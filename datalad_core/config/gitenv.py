from __future__ import annotations

from contextlib import contextmanager
from typing import (
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    from collections.abc import (
        Collection,
        Generator,
        Hashable,
    )

from datasalad.settings import (
    Setting,
    UnsetValue,
    WritableMultivalueSource,
)

from datalad_core.config.item import ConfigItem
from datalad_core.config.utils import (
    get_gitconfig_items_from_env,
    set_gitconfig_items_in_env,
)


class GitEnvironment(WritableMultivalueSource):
    """Source for Git's environment variable based ``command`` scope

    This class provides an interface to get and set (multivalued) configuration
    items in the process environment via ``GIT_CONFIG_KEY/VALUE`` variables.
    This mechanism is provided by ``git config``, hence any such manipulations
    directly affect all git-based child processes, too.

    This implementation is intentionally stateless to avoid any syncronicity
    issues from multiple agent manipulating the environment during
    the runtime of a process. The method :meth:`overrides`
    provides a context manager for setting temporary configuration.
    """

    item_type = ConfigItem

    def __str__(self) -> str:
        return self.__class__.__name__

    def _reinit(self):
        """Does nothing"""

    def _load(self) -> None:
        """Does nothing

        All accessors inspect the process environment directly.
        """

    def _get_item(self, key: Hashable) -> Setting:
        val = get_gitconfig_items_from_env()[str(key)]
        if isinstance(val, tuple):
            return self.item_type(val[-1])
        return self.item_type(val)

    def _set_item(self, key: Hashable, value: Setting) -> None:
        env = get_gitconfig_items_from_env()
        env[str(key)] = str(value.value)
        set_gitconfig_items_in_env(env)

    def _del_item(self, key: Hashable) -> None:
        env = get_gitconfig_items_from_env()
        del env[str(key)]
        set_gitconfig_items_in_env(env)

    def _get_keys(self) -> Collection:
        return get_gitconfig_items_from_env().keys()

    def _getall(
        self,
        key: Hashable,
    ) -> tuple[Setting, ...]:
        val = get_gitconfig_items_from_env()[str(key)]
        vals = val if isinstance(val, tuple) else (val,)
        return tuple(self.item_type(v) for v in vals)

    def _setall(self, key: Hashable, values: tuple[Setting, ...]) -> None:
        key_str = str(key)
        prepped_values = tuple(str(v.value) for v in values)
        env = get_gitconfig_items_from_env()
        env[key_str] = prepped_values
        set_gitconfig_items_in_env(env)

    @contextmanager
    def overrides(
        self,
        overrides: dict[Hashable, Setting | tuple[Setting, ...]],
    ) -> Generator[None]:
        """Context manager to temporarily set configuration overrides"""
        restore: dict[Hashable, tuple[Setting, ...]] = {}

        for k, v in overrides.items():
            restore[k] = self.getall(k, self.item_type(UnsetValue))
            if isinstance(v, tuple):
                self.setall(k, v)
            else:
                self[k] = v
        try:
            yield
        finally:
            # NOTE: coverage is falsely reported as absent for PY3.9
            # https://github.com/nedbat/coveragepy/issues/1292
            # we disable the coverage error report below. To convince
            # yourself that this is covered, just introduce a syntax
            # error
            for k, vals in restore.items():  # pragma: no cover
                if len(vals) == 1 and vals[0].pristine_value is UnsetValue:
                    del self[k]
                    break
                self.setall(k, vals)
