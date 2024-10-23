from __future__ import annotations

from contextlib import contextmanager
from typing import (
    TYPE_CHECKING,
    Any,
)

if TYPE_CHECKING:
    from collections.abc import (
        Generator,
        Hashable,
    )

    from datasalad.settings import Source

from datasalad.settings import (
    Setting,
    Settings,
    UnsetValue,
)

from datalad_core.config.defaults import (
    ImplementationDefaults,
    get_defaults,
)
from datalad_core.config.git import (
    GlobalGitConfig,
    SystemGitConfig,
)
from datalad_core.config.gitenv import GitEnvironment
from datalad_core.config.item import ConfigItem


class ConfigManager(Settings):
    """Multi-source (scope) configuration manager

    By default (``source=None``), a manager utilizes a fixed (order) collection
    of sources (from highest to lowest precedence):

    - ``git-command``: :class:`GitEnvironment`
    - ``git-global``: :class:`GlobalGitConfig`
    - ``git-system``: :class:`SystemGitConfig`
    - ``defaults``: :class:`ImplementationDefaults`

    If a different source collection is desired, it can be given as
    ``sources``.  The ``default`` source will be added to the given sources.
    """

    def __init__(
        self,
        defaults: ImplementationDefaults,
        # TODO: should be Mapping[str, Source] | None
        sources: dict[str, Source] | None = None,
    ):
        if sources is None:
            sources = {
                # call this one 'command', because that is what Git calls the
                # scope of items pulled from the process environment
                'git-command': GitEnvironment(),
                'git-global': GlobalGitConfig(),
                'git-system': SystemGitConfig(),
            }
        sources['defaults'] = defaults
        super().__init__(sources)
        # set .item_type for all sources, such that any plain default
        # comes back wrapped in the same item type
        for s in self.sources.values():
            s.item_type = ConfigItem

    def __str__(self) -> str:
        return (
            f'{self.__class__.__name__}('
            # aim for a compact display, leave our sources with no content
            f'{"<<".join(str(s) for s in self.sources.values() if len(s))}'
            ')'
        )

    def __repr__(self) -> str:
        # just like __str__, but does not trim sources without content
        return (
            f'{self.__class__.__name__}('
            f'{"<<".join(str(s) for s in self.sources.values())}'
            ')'
        )

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

    # TODO: migrate this implementation to datasalad.Settings
    def get(self, key: Hashable, default: Any = None) -> Setting:
        """Return a particular setting identified by its key, or a default

        The composition of the returned setting follows the same rules
        as the access via ``__getitem__``. However, if the effective
        ``pristine_value`` retrieved from any existing configuration is
        ``UnsetValue``, it is update with the given default.

        When the ``default`` value is not given as an instance of
        :class:`~datasalad.settings.Setting`, it will be
        automatically wrapped into the one given by :attr:`Settings.item_type`.
        """
        try:
            val = self[key]
        except KeyError:
            return self._get_default_setting(default)

        if val.pristine_value is UnsetValue:
            val.update(self._get_default_setting(default))
        return val


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
