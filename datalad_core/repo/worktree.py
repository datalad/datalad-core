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
from datalad_core.repo.gitmanaged import GitManaged
from datalad_core.repo.repo import Repo


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
