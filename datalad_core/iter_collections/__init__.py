"""Iterators for particular types of collections

Most, if not all, implementation come in the form of a function that takes
a collection identifier or a collection location (e.g., a file system path),
and possibly some additional options. When called, an iterator is returned
that produces collection items in the form of data class instances of
a given type. The particular type can be different across different
collections.


.. currentmodule:: datalad_core.iter_collections
.. autosummary::
   :toctree: generated

   iter_gitworktree
   GitTreeItemType
   GitWorktreeItem
"""

__all__ = [
    'GitTreeItemType',
    'GitWorktreeItem',
    'iter_gitworktree',
]

from .gitworktree import (
    GitTreeItemType,
    GitWorktreeItem,
    iter_gitworktree,
)
