from __future__ import annotations

from dataclasses import dataclass
from pathlib import (
    Path,
    PurePosixPath,
)

from datalad_core.repo import GitTreeItemType, Worktree


@dataclass(frozen=True)
class WorktreeDirectory:
    """Directory in a worktree

    This class links a particular (relative) directory (path) to the
    worktree that contains it. The primary use of this class is to capture
    the context of an operation that is not performed against the root
    of a worktree, and simultaneously avoid that the context worktree
    has to be resolved repeatedly.
    """

    worktree: Worktree
    """Worktree reference to anchor the ``relpath`` property"""
    relpath: PurePosixPath
    """Path of the directory, relative to the root of the ``worktree``"""

    @property
    def path(self) -> Path:
        """Returns the full path, resolved against the worktree"""
        return self.worktree.path / self.relpath

    @staticmethod
    def from_path(path: Path) -> WorktreeDirectory:
        """Create a ``WorktreeDirectory`` instance from a path

        The worktree that contains the path is resolved, and
        the given path is converted to be relative to the worktree
        root.
        """
        wt = Worktree(path)
        relpath = PurePosixPath(path.relative_to(wt.path))
        return WorktreeDirectory(wt, relpath)


@dataclass(frozen=True)
class WorktreeItem:
    """Item in a Git worktree/checkout

    The ``basedir`` property associates the item with a concrete worktree
    (location) on the filesystem. The item itself is identified by its
    path relative to this base directory.

    A :class:`Worktree` instance is accessible via ``.basedir.worktree``.

    The two optional properties ``gitsha`` and ``gittype`` annotate worktree
    items whenever the information is known.
    """

    basedir: WorktreeDirectory
    """``Path`` of the tree the item is part of"""
    relpath: PurePosixPath
    """Path of the item relative to the ``tree_path``"""
    gitsha: str | None = None
    """Git's SHA identifier for the item, if known"""
    gittype: GitTreeItemType | None = None
    """Item type identifier, if known"""

    @property
    def path(self) -> Path:
        """Platform path of the item"""
        return self.basedir.path / self.relpath
