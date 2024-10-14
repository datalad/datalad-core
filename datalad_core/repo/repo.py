from __future__ import annotations

from typing import TYPE_CHECKING
from weakref import (
    WeakValueDictionary,
    finalize,
)

if TYPE_CHECKING:
    from pathlib import Path

from datasalad.settings import Settings

from datalad_core.config import (
    ConfigItem,
    ConfigManager,
    DataladBranchConfig,
    LocalGitConfig,
    get_manager,
)
from datalad_core.repo.gitmanaged import GitManaged


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
            # we want to bypass all the source creations in the constructor,
            # and instead reuse them here to get cheap synchronization with
            # a "parent" manager
            lman = Settings.__new__(ConfigManager)
            Settings.__init__(
                lman,
                {
                    'git-command': gman.sources['git-command'],
                    'git-local': loc,
                    'git-global': gman.sources['git-global'],
                    'git-system': gman.sources['git-system'],
                    'datalad-branch': dlbranch,
                    'defaults': gman.sources['defaults'],
                },
            )
            self._config = lman
        return self._config
