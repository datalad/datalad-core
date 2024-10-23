from __future__ import annotations

from typing import TYPE_CHECKING
from weakref import (
    WeakValueDictionary,
    finalize,
)

if TYPE_CHECKING:
    from pathlib import Path


from datalad_core.config import (
    ConfigItem,
    ConfigManager,
    DataladBranchConfig,
    LocalGitConfig,
    get_manager,
)
from datalad_core.repo.annex import BareRepoAnnex
from datalad_core.repo.gitmanaged import GitManaged
from datalad_core.repo.utils import init_annex_at
from datalad_core.runners import call_git


class Repo(GitManaged):
    """(The bare part of) an existing repository"""

    # flyweights
    _unique_instances: WeakValueDictionary = WeakValueDictionary()

    def __init__(self, path: Path):
        """
        ``path`` is the path to an existing repository (Git dir).
        """
        super().__init__(path)
        self.reset()

        # TODO: sanity check with: `git rev-parse --is-inside-git-dir <path>`?

        # Register a finalizer (instead of having a __del__ method).  This will
        # be called by garbage collection as well as "atexit". By keeping the
        # reference here, we could also call it explicitly... eventually
        self._finalizer = finalize(self, Repo._close, self.path)

    def reset(self) -> None:
        super().reset()
        self._config: ConfigManager | None = None
        self._annex: BareRepoAnnex | None = None

    @property
    def config(self) -> ConfigManager:
        """Returns a ``ConfigManager`` tailored to the repository

        The returned instance reuses all source instances of the global
        manager. In addition, a :class:`LocalGitConfig`, and
        :class:`DataladBranchConfig` source are included in the list of
        scopes. The order of sources is:

        - ``git-command``: :class:`GitEnvironment`
        - ``git-local``: :class:`LocalGitConfig`
        - ``git-global``: :class:`GlobalGitConfig`
        - ``git-system``: :class:`SystemGitConfig`
        - ``datalad-branch``: :class:`DataladBranchConfig`
        - ``defaults``: :class:`ImplementationDefaults`
        """
        if self._config is None:
            gman = get_manager()
            # would raise ValueError, if there is no repo at `path`
            loc = LocalGitConfig(self.path)
            dlbranch = DataladBranchConfig(self.path)
            for s in (loc, dlbranch):
                s.item_type = ConfigItem
            lman = ConfigManager(
                defaults=gman.sources['defaults'],
                sources={
                    'git-command': gman.sources['git-command'],
                    'git-local': loc,
                    'git-global': gman.sources['git-global'],
                    'git-system': gman.sources['git-system'],
                    'datalad-branch': dlbranch,
                },
            )
            # the local scope is fully controlled by the executing user.
            # the 'datalad-branch' on the other hand can update with any merge
            # based on external changes. This is not protected.
            lman.declare_source_protected('git-local')
            self._config = lman
        return self._config

    def init_annex(
        self,
        description: str | None = None,
        *,
        autoenable_remotes: bool = True,
    ) -> BareRepoAnnex:
        """ """
        if self.config.get('core.bare', False).value is False:
            msg = (
                'Cannot initialize annex in a non-bare repository, '
                'use Worktree.init_annex()'
            )
            raise TypeError(msg)
        init_annex_at(
            self.path,
            description=description,
            autoenable_remotes=autoenable_remotes,
        )
        annex = self.bare_annex
        if annex is None:  # pragma: no cover
            msg = 'could not initialize annex unexpectedly'
            raise RuntimeError(msg)
        return annex

    # we name this "bare_annex" not just "annex", even though it is clunky,
    # to avoid the confusions associated with "but it has an annex, it is
    # just not a bare respoitory"
    @property
    def bare_annex(self) -> BareRepoAnnex | None:
        """Handler for a bare repository's annex

        If there is no initialized annex, or the repository is not bare,
        this will be ``None``.

        To get a handler for a non-bare repository's annex use
        :attr:`Worktree.annex`.
        """
        if self.config.get('core.bare', False).value is False:
            return None
        if self._annex is None:
            try:
                self._annex = BareRepoAnnex(self.path)
            except ValueError:
                # resetting it to None means that we will keep trying to
                # locate an annex each time. I believe this is a sensible
                # behavior. A once-present annex is unlikely to go away,
                # but an annex could be initialized at any time
                self._annex = None
        return self._annex

    @classmethod
    def init_at(cls, path: Path) -> Repo:
        """Initialize a bare repository in an existing directory

        There is no test for an existing repository at ``path``. A potential
        reinitialization is generally safe. Use cases are described in the
        ``git init`` documentation.
        """
        # TODO: support --shared, needs to establish ENUM for options
        call_git(
            ['init', '--bare'],
            cwd=path,
            capture_output=True,
        )
        return cls(path)
