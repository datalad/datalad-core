"""Configuration management

This module provides the standard facilities for configuration management,
query, and update. It is built on `datasalad.settings
<https://datasalad.readthedocs.io/latest/generated/datasalad.settings.html>`__.

The key piece is the :class:`ConfigManager` that supports querying for
configuration settings across multiple sources. It also offers a context
manager to temporarily override particular configuration items.

With the method :meth:`ConfigManager.for_dataset`, a manager instance tailored
to a specific dataset can be created. A "dataset" in this context is any
Git repository, with or without an initialized annex, and with or without
initialization as a DataLad dataset. Such an instance will share all sources
of the original manager instance, and supports additional sources for the
scopes of repository-local Git configuration, and branch-committed DataLad
configuration.

Usage
-----

Basic usage is more or less identical to that of the ``datasalad.settings``.
Importantly, and unlike the legacy DataLad approach, no instance of
:class:`~datalad_core.config.ConfigManager` is provided. Instead, if and when
such a common instance it needed, it must be obtained by calling
:func:`get_manager`. This is typically done first by a respective "entrypoint"
implementation. Subsequent calls will return the same instance.

The same pattern is applied to obtain a common instance of
:class:`ImplementationDefaults` via :func:`get_defaults`. This instance
can be used to register defaults for any and all configuration settings
supported by a particular implementation. This can be done on importing
the respective modules.


.. currentmodule:: datalad_core.config
.. autosummary::
   :toctree: generated

   ConfigItem
   ConfigManager
   GitConfig
   SystemGitConfig
   GlobalGitConfig
   LocalGitConfig
   DataladBranchConfig
   WorktreeGitConfig
   GitEnvironment
   ImplementationDefaults
   UnsetValue
   get_defaults
   get_manager
"""

__all__ = [
    'ConfigItem',
    'ConfigManager',
    'GitConfig',
    'SystemGitConfig',
    'GlobalGitConfig',
    'LocalGitConfig',
    'DataladBranchConfig',
    'WorktreeGitConfig',
    'GitEnvironment',
    'ImplementationDefaults',
    'UnsetValue',
    'get_defaults',
    'get_manager',
]

from datasalad.settings import UnsetValue

from .defaults import (
    ImplementationDefaults,
    get_defaults,
)
from .git import (
    DataladBranchConfig,
    GitConfig,
    GlobalGitConfig,
    LocalGitConfig,
    SystemGitConfig,
    WorktreeGitConfig,
)
from .gitenv import GitEnvironment
from .item import ConfigItem
from .manager import (
    ConfigManager,
    get_manager,
)
