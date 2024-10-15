from __future__ import annotations

from typing import TYPE_CHECKING
from weakref import WeakValueDictionary

if TYPE_CHECKING:
    from pathlib import Path

from datasalad.settings import Settings

from datalad_core.config import (
    ConfigItem,
    ConfigManager,
    WorktreeGitConfig,
)
from datalad_core.repo.annex import Annex
from datalad_core.repo.gitmanaged import GitManaged
from datalad_core.repo.repo import Repo
from datalad_core.repo.utils import init_annex_at
from datalad_core.runners import call_git


class Worktree(GitManaged):
    """Git worktree (checkout)

    A worktree is the primary checkout (of a non-bare) Git repository, or any
    (linked) additional Git worktree. A :class:`Worktree` instance always has
    an associated :class:`Repo`, accessible via its :attr:`repo` property.
    """

    # flyweights
    _unique_instances: WeakValueDictionary = WeakValueDictionary()

    def __init__(
        self,
        path: Path,
    ):
        super().__init__(path)
        self.reset()

    def reset(self) -> None:
        super().reset()
        self._annex: Annex | None = None
        self._config: ConfigManager | None = None
        self._repo: Repo | None = None

    @property
    def config(self) -> ConfigManager:
        """Config manager for the worktree

        The manager supports additional ``git-local`` and possibly
        ``git-worktree`` scopes (if ``extensions.worktreeConfig`` is enabled,
        see :meth:`enable_worktree_config`).

        Source instances for all other scopes are shared with the global
        configuration manager.

        The order of sources is:

        - ``git-command``: :class:`GitEnvironment`
        - ``git-worktree``: :class:`WorktreeGitConfig` (if enabled)
        - ``git-local``: :class:`LocalGitConfig`
        - ``git-global``: :class:`GlobalGitConfig`
        - ``git-system``: :class:`SystemGitConfig`
        - ``datalad-branch``: :class:`DataladBranchConfig`
        - ``defaults``: :class:`ImplementationDefaults`

        """
        if self._config is None:
            rman = self.repo.config
            if rman.get('extensions.worktreeConfig', False).value is False:
                # worktree config extension is not enabled, we can simply
                # reuse the repo manager with its local scope
                self._config = self.repo.config
                return self._config

            wt = WorktreeGitConfig(self.path)
            wt.item_type = ConfigItem
            # we want to bypass all the source creations in the constructor,
            # and instead reuse them here to get cheap synchronization with
            # a "parent" manager
            lman = Settings.__new__(ConfigManager)
            Settings.__init__(
                lman,
                {
                    'git-command': rman.sources['git-command'],
                    'git-worktree': wt,
                    'git-local': rman.sources['git-local'],
                    'git-global': rman.sources['git-global'],
                    'git-system': rman.sources['git-system'],
                    'datalad-branch': rman.sources['datalad-branch'],
                    'defaults': rman.sources['defaults'],
                },
            )

            self._config = lman
        return self._config

    def enable_worktree_config(self):
        """Enable ``extensions.worktreeConfig`` for Git config

        The corresponding setting is put into the ``git-local`` scope and a
        reinitialization of :attr:`config` property for the worktree instance
        is triggered, to start supporting a dedicated ``git-worktree``
        scope for reading and writing.

        If ``extensions.worktreeConfig`` was already enabled, this
        method does nothing.
        """
        if 'git-worktree' in self.config.sources:
            return

        self.config.sources['git-local'][
            # we use snake casing here. the section/variable
            # name is case-insensitive, and it must not matter
            'extensions.worktreeConfig'
        ] = ConfigItem('true')
        self._config = None

    @property
    def repo(self) -> Repo:
        """Returns the underlying repository

        For a linked worktree, this is the shared repository (GIT_COMMON_DIR),
        not the worktree-specific administrative Git directory (GIT_DIR).
        """
        if self._repo is None:
            self._repo = Repo(self.git_common_dir)
        return self._repo

    def init_annex(
        self,
        description: str | None = None,
        *,
        autoenable_remotes: bool = True,
    ) -> Annex:
        """ """
        # refuse for non-bare
        init_annex_at(
            self.path,
            description=description,
            autoenable_remotes=autoenable_remotes,
        )
        annex = self.annex
        if annex is None:  # pragma: no cover
            msg = 'could not initialize annex unexpectedly'
            raise RuntimeError(msg)
        return annex

    @property
    def annex(self) -> Annex | None:
        if self._annex is None:
            try:
                self._annex = Annex(self.path)
            except ValueError:
                # resetting it to None means that we will keep trying to
                # locate an annex each time. I believe this is a sensible
                # behavior. A once-present annex is unlikely to go away,
                # but an annex could be initialized at any time
                self._annex = None
        return self._annex

    @classmethod
    def init_at(cls, path: Path, gitdir: Path | None = None) -> Worktree:
        """Initialize a worktree for a new/existing repository in a directory

        A worktree will be (re)initialized at ``path``.

        If ``gitdir`` is given it will be passed to
        ``git init --separate-git-dir``. Depending on whether the location at
        ``path`` has already been initialized, an existing repository will
        be relocated (see ``git init`` documentation).
        """
        cmd = ['init']
        if gitdir is not None:
            cmd.extend(('--separate-git-dir', str(gitdir)))
        # TODO: support --shared, needs to establish ENUM for options
        call_git(
            cmd,
            cwd=path,
            capture_output=True,
        )
        wt = cls(path)
        if gitdir is not None:
            # this call could have relocated the underlying repo.
            # drop all previous references and evaluate from scratch.
            # we could do upfront inspection instead, but this is
            # reasonably cheap, and safeer to do unconditionally.
            wt.repo.reset()
            wt.reset()
        return wt