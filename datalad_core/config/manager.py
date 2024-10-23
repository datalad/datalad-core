from __future__ import annotations

from contextlib import contextmanager
from copy import copy
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
        # explicit collection of source keys that will be considered for
        # get_from_protected_sources()
        # we are not doing self.sources.keys(), because that would auto-add
        # any new sources to this list, and we require an explicit decision,
        # because this is choice with security impact (think source that
        # pull information from places that the executing user is not
        # trusting)
        self._protected_source_keys: set[str] = {
            # controlled by the executing user
            'git-command',
            # owned by the executing user
            'git-global',
            # controlled by super user (implicit trust)
            'git-system',
            # there is implicit trust, any code executed
            # in this process can, in principle, alter
            # any configuration
            'defaults',
        }

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

    # TODO: a generic variant could migrate to datasalad.Settings
    # (from select sources)
    def get_from_protected_sources(
        self,
        key: Hashable,
        default: Any = None,
    ) -> Setting:
        """Return a particular setting from protected sources only

        This methods behaves like :meth`get`, but it considering
        only sources that have been declared as ``protected``.
        Thereby, this method can be used to query for security-related
        configuration from a limited set of source.

        By default, protected sources are:

        - ``git-command``
        - ``git-global``
        - ``git-system``
        - ``defaults``

        Additional sources can be declared ``protected`` via
        :meth:`declare_source_protected`.

        This should only be to for sources where the executing
        user (or an entity with elevated privileges) has exclusive
        write permissions, to prevent undesired and unvetted
        configuration changes.
        """
        # this will become the return item
        item: Setting | None = None
        # now go from the back
        # - start with the first Setting class instance we get
        # - update a copy of this particular instance with all information
        #   from sources with higher priority and flatten it across
        #   sources
        for sk in reversed(self._sources):
            if sk not in self._protected_source_keys:
                continue
            s = self._sources[sk]
            update_item = None
            try:
                update_item = s[key]
            except KeyError:
                # source does not have it, proceed
                continue
            if item is None:
                # in-place modification and destroy the original
                # item's integrity
                item = copy(update_item)
                continue
            # we run the update() method of the first item we ever found.
            # this will practically make the type produced by the lowest
            # precedence source define the behavior. This is typically
            # some kind of implementation default
            item.update(update_item)
        if item is None:
            item = self._get_default_setting(default)
        if item.pristine_value is UnsetValue:
            item.update(self._get_default_setting(default))
        return item

    def declare_source_protected(self, key: str):
        """Add the source identified by `key` to the set of "protected" sources

        This qualifies them for being queried by
        :meth:`get_from_protected_sources`.

        Declaring sources as "protected" has to be done with care.
        :meth:`get_from_protected_sources` is queried for security-related
        decision making. It is important to not declare sources is protected
        that are not controlled by the executing user, or that the user
        already has to trust.

        An example of sources that should NOT be declared protected are any
        that update (automatically) from information not set explicitly by the
        executing user alone (requests to web service, dataset content
        possibly merged unverfied from contributors, etc).
        """
        if key not in self._sources:
            msg = f'{key} is not a known configuration source'
            raise ValueError(msg)
        self._protected_source_keys.add(key)


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
