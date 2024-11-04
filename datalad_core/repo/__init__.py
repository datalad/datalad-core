"""Repository and worktree representations

This module provides the essential types for working with Git/git-annex
repositories and DataLad datasets.

For most use cases, the :class:`Worktree` class is the main entrypoint.  It can
be pointed to an existing Git repository checkout, or a new repository can be
created via its :meth:`Worktree.init_at` class method.  Access to operations on
the underlying Git repository (that may be shared by additional worktrees) is
possible via the :attr:`Worktree.repo` attribute. An optional (git-)annex can
be initialized (:meth:`Worktree.init_annex`), and accessed via
:attr:`Worktree.annex`.

Working with bare Git repositories is supported by using the :class:`Repo`
class directly. Operations on an annex of a bare repository are accessible
via the :attr:`Repo.bare_annex` attribute.

The :class:`Repo` and :class:`Worktree` classes in this module implement the
"flyweight" pattern.  This means that, within the same process, creating
instances of :class:`Repo` and :class:`Worktree` always yields the same
instance for the same path location.

.. currentmodule:: datalad_core.repo
.. autosummary::
   :toctree: generated

   Repo
   Worktree
   Annex
   BareRepoAnnex
   GitTreeItem
   GitTreeItemType
   Treeish
   WorktreeDirectory
   WorktreeItem
"""

__all__ = [
    'Repo',
    'Worktree',
    'Annex',
    'BareRepoAnnex',
    'GitTreeItem',
    'GitTreeItemType',
    'Treeish',
    'WorktreeDirectory',
    'WorktreeItem',
]

from .annex import (
    Annex,
    BareRepoAnnex,
)
from .repo import Repo
from .tree_item import (
    GitTreeItem,
    GitTreeItemType,
    Treeish,
)
from .worktree import Worktree
from .worktree_item import (
    WorktreeDirectory,
    WorktreeItem,
)
