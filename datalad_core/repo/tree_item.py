from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import PurePosixPath

    from datalad_core.repo import Repo


# TODO: Could be `StrEnum`, came with PY3.11
class GitTreeItemType(Enum):
    """Enumeration of item types of Git trees"""

    file = 'file'
    executablefile = 'executablefile'
    symlink = 'symlink'
    directory = 'directory'
    submodule = 'submodule'


git_mode_type_map = {
    '100644': GitTreeItemType.file,
    '100755': GitTreeItemType.executablefile,
    '040000': GitTreeItemType.directory,
    '120000': GitTreeItemType.symlink,
    '160000': GitTreeItemType.submodule,
}


@dataclass(frozen=True)
class Treeish:
    """Git tree object reference

    A tree-ish in Git's terminology is a tree object or an object that can be
    recursively dereferenced to a tree object. Dereferencing a commit object
    yields the tree object corresponding to the revision's top directory. The
    following are all tree-ishes: a commit-ish, a tree object, a tag object
    that points to a tree object, a tag object that points to a tag object that
    points to a tree object, etc.

    .. note:: Limited support for Git's tree-ish types

       This class requires an explicit association of the tree-ish with a
       repository that does or will contain the tree-ish. This forced
       association is important for disambiguating tree-ishes across
       repositories (e.g., in a DataLad dataset hierarchy).

       Therefore, this representation of a tree-ish is conceptually
       incompatible with Git's CWD-relative tree-ishes, such as
       ``HEAD:./path`` that are to be interpreted relative to the
       working directory of a process.

    """

    repo: Repo
    """Repository that the tree is part of"""
    treeish: str
    """Identifier of the tree within the repository context

    This can be any revision identifier (e.g., ``HEAD``, a branch/tag name,
    etc), or a tree identifier (e.g., ``<revision>:<relpath>``).  If given, the
    ``relpath`` component must not be empty and must not start with ``./`` or
    ``../``. This indicates a location relative to CWD, but the tree must be
    fully identified given ``repo`` and ``treeish`` alone, regardless of CWD.
    """

    def get_item_id(self, relpath: PurePosixPath) -> str:
        """Returns a suitable blob or tree identifier for an item of the tree

        The tree item is identified by its path relative to the tree root
        (``relpath``).
        """

        return (
            f'{self.treeish.rstrip("/")}/{relpath}'
            if ':' in self.treeish
            else f'{self.treeish}:{relpath}'
        )


@dataclass(frozen=True)
class GitTreeItem:
    """Item in a Git tree

    This dataclass represents a (prospective) tree item. For concrete items,
    the optional properties ``gitsha`` and ``gittype`` can be set. Without
    these and instance of this class can be used to build a subtree in a
    Git repository.
    """

    tree: Treeish
    """The tree that contains the item"""
    relpath: PurePosixPath
    """Path of the item relative to ``tree``"""

    # gitsha is not the sha1 of the file content, but the output
    # of `git hash-object` which does something like
    # `printf "blob $(wc -c < "$file_name")\0$(cat "$file_name")" | sha1sum`
    gitsha: str | None = None
    """GITSHA identifier of the tree item, if known"""
    gittype: GitTreeItemType | None = None
    """Type (or mode) identifier of the tree item, if known"""

    @property
    def object_id(self) -> str:
        """Returns a suitable blob or tree identifier for the item

        This identifier can used with Git commands such as ``git cat-file``
        as an alternative to the GITSHA.
        """

        return self.tree.get_item_id(self.relpath)

    @staticmethod
    def mode2type(mode: str) -> GitTreeItemType:
        """Convert a Git mode string to a ``GitTreeItemType``"""
        return git_mode_type_map[mode]
