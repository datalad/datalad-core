from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import (
        Generator,
        Hashable,
    )
    from pathlib import Path

from datasalad.settings import (
    Setting,
    Settings,
)

from datalad_core.config.defaults import (
    ImplementationDefaults,
    get_defaults,
)
from datalad_core.config.git import (
    DataladBranchConfig,
    GlobalGitConfig,
    LocalGitConfig,
    SystemGitConfig,
)
from datalad_core.config.gitenv import GitEnvironment
from datalad_core.config.item import ConfigurationItem


class ConfigManager(Settings):
    """Multi-source (scope) configuration manager

    This manager utilizes a fixed (order) collection of source (from
    highest to lowest precedence):

    - ``git-command``: :class:`GitEnvironment`
    - ``git-global``: :class:`GlobalGitConfig`
    - ``git-system``: :class:`SystemGitConfig`
    - ``defaults``: :class:`ImplementationDefaults`
    """

    def __init__(self, defaults: ImplementationDefaults):
        super().__init__(
            {
                # call this one 'command', because that is what Git calls the scope
                # of items pulled from the process environment
                'git-command': GitEnvironment(),
                'git-global': GlobalGitConfig(),
                'git-system': SystemGitConfig(),
                'defaults': defaults,
            }
        )
        # set .item_type for all sources, such that any plain default
        # comes back wrapped in the same item type
        for s in self.sources.values():
            s.item_type = ConfigurationItem

    @contextmanager
    def overrides(
        self,
        overrides: dict[Hashable, Setting | tuple[Setting, ...]],
    ) -> Generator[ConfigManager]:
        """Context manager to temporarily set configuration overrides

        Internally, these overrides are posted to the ``git-command`` scope,
        hence affect the process environment and newly spawned subprocesses.
        """
        gitcmdsrc = self.sources['git-command']
        with gitcmdsrc.overrides(overrides):
            yield self

    def for_dataset(self, path: Path) -> ConfigManager:
        """Returns a ``ConfigManager`` tailored to a specific dataset

        The returned instance reuses all source instances of the original
        manager. In addition, a :class:`LocalGitConfig`, and :class:`DataladBranchConfig` source are included in the list of scopes. The order of sources is:

        - ``git-command``: :class:`GitEnvironment`
        - ``git-local``: :class:`LocalGitConfig`
        - ``git-global``: :class:`GlobalGitConfig`
        - ``git-system``: :class:`SystemGitConfig`
        - ``datalad-branch``: :class:`DataladBranchConfig`
        - ``defaults``: :class:`ImplementationDefaults`

        There is no built-in (singleton) instance management. Each call
        to this method returns a new instance with new source instances
        for the ``git-local`` and ``datalad-branch`` scopes.
        """
        # we want to bypass all the source creations in the constructor,
        # and instead reuse them here to get cheap synchronization with
        # a "parent" manager
        dm = Settings.__new__(self.__class__)
        # would raise ValueError, if there is no repo at `path`
        loc = LocalGitConfig(path)
        dlbranch = DataladBranchConfig(path)
        for s in (loc, dlbranch):
            s.item_type = ConfigurationItem
        Settings.__init__(
            dm,
            {
                'git-command': self.sources['git-command'],
                'git-local': loc,
                'git-global': self.sources['git-global'],
                'git-system': self.sources['git-system'],
                'datalad-branch': dlbranch,
                'defaults': self.sources['defaults'],
            },
        )
        return dm


__the_manager: ConfigManager | None = None


def get_manager() -> ConfigManager:
    """Return a a process-unique, global `ConfigManager` instance

    This function can be used obtain a :class:`ConfigManager`
    instance for query and manipulation of settings.
    """
    global __the_manager  # noqa: PLW0603
    if __the_manager is None:
        __the_manager = ConfigManager(get_defaults())
    return __the_manager
