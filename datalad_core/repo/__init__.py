"""Repository and worktree representations

The classes in this module implement the "flyweight" pattern.  This means that,
within the same process, creating instances of :class:`Repo` and
:class:`Worktree` always yields the same instance for the same path location.

.. currentmodule:: datalad_core.repo
.. autosummary::
   :toctree: generated

   Repo
   Worktree
"""

__all__ = [
    'Repo',
    'Worktree',
]

from .repo import Repo
from .worktree import Worktree
