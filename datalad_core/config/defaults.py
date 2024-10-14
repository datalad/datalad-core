from __future__ import annotations

from datasalad.settings import (
    Defaults,
)
from datasalad.settings import (
    UnsetValue as Unset,
)

from datalad_core.config.item import ConfigItem as Item


class ImplementationDefaults(Defaults):
    """Source for registering implementation defaults of settings

    This is a in-memory only source that is populated by any
    implementations that want to expose their configuration
    options."""

    def __str__(self):
        return 'ImplementationDefaults'


__the_defaults: ImplementationDefaults | None = None


def get_defaults() -> ImplementationDefaults:
    """Return a a process-unique `ImplementationDefault` instance

    This function can be used obtain a :class:`ImplementationDefaults`
    instance for setting and/or getting defaults for settings.
    """
    global __the_defaults  # noqa: PLW0603
    if __the_defaults is None:
        __the_defaults = ImplementationDefaults()
        register_defaults_gitcfg(__the_defaults)
    return __the_defaults


def register_defaults_gitcfg(defaults: ImplementationDefaults) -> None:
    for k, v in _gitcfg.items():
        defaults[k] = v


def anything2bool(val):
    if val == '':
        return False
    if hasattr(val, 'lower'):
        val = val.lower()
    if val in {'off', 'no', 'false', '0'} or not bool(val):
        return False
    if (
        val in {'on', 'yes', 'true', True}
        or (hasattr(val, 'isdigit') and val.isdigit() and int(val))
        or isinstance(val, int)
        and val
    ):
        return True
    msg = f'Cannot interpret {val!r} as a boolean'
    raise ValueError(msg)


_gitcfg = {
    'core.bare': Item(Unset, coercer=anything2bool),
    'extensions.worktreeConfig': Item(Unset, coercer=anything2bool),
}
