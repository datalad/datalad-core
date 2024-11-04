from __future__ import annotations

from dataclasses import dataclass
from pathlib import (
    Path,
    PurePosixPath,
)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator

from datalad_core.iter_collections.utils import (
    GitTreeItemType,
    git_ls_tree,
    git_mode_type_map,
)


@dataclass(frozen=True)
class GitTreeItem:
    """Item in a Git tree"""

    relpath: PurePosixPath
    # gitsha is not the sha1 of the file content, but the output
    # of `git hash-object` which does something like
    # `printf "blob $(wc -c < "$file_name")\0$(cat "$file_name")" | sha1sum`
    gitsha: str | None = None
    gittype: GitTreeItemType | None = None


def iter_gittree(
    path: Path,
    treeish: str,
    *,
    recursion: str = 'repository',
) -> Generator[GitTreeItem]:
    """Uses ``git ls-tree`` to report on a tree in a Git repository

    Parameters
    ----------
    path: Path
      Path of a directory in a Git repository to report on. This directory
      need not be the root directory of the repository, but must be part of
      the repository. If the directory is not the root directory of a
      non-bare repository, the iterator is constrained to items underneath
      that directory.
    recursion: {'repository', 'none'}, optional
      Behavior for recursion into subtrees. By default (``repository``),
      all tree within the repository underneath ``path``) are reported,
      but not tree within submodules. If ``none``, only direct children
      are reported on.

    Yields
    ------
    :class:`GitTreeItem`
      The ``name`` attribute of an item is a ``str`` with the corresponding
      (relative) path, as reported by Git (in POSIX conventions).
    """
    # we force-convert to Path to give us the piece of mind we want.
    # The docs already ask for that, but it is easy to
    # forget/ignore and leads to non-obvious errors. Running this once is
    # a cheap safety net
    path = Path(path)

    # although it would be easy to also query the object size, we do not
    # do so, because it has a substantial runtime impact. It is unclear
    # what the main factor for the slowdown is, but in test cases I can
    # see 10x slower
    # lstree_args = ['--long']
    # we do not go for a custom format that would allow for a single split
    # by tab, because if we do, Git starts quoting paths with special
    # characters (like tab) again
    # lstree_args = ['--format=%(objectmode)%x09%(objectname)%x09%(path)']
    lstree_args = []
    if recursion == 'repository':
        lstree_args.append('-r')

    for line in git_ls_tree(path, treeish, *lstree_args):
        yield _get_tree_item(line)


def _get_tree_item(spec: str) -> GitTreeItem:
    props, path = spec.split('\t', maxsplit=1)
    # 0::2 gets the first and third (last) item, effectively skippping the
    # type name (blob/tree etc.), we have the mode lookup for that, which
    # provides more detail
    mode, sha = props.split(' ')[0::2]
    return GitTreeItem(
        relpath=PurePosixPath(path),
        gitsha=sha,
        gittype=git_mode_type_map[mode],
    )
