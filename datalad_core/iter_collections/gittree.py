from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator

from datalad_core.iter_collections.utils import git_ls_tree
from datalad_core.repo import (
    GitTreeItem,
    Treeish,
)


def iter_gittree(
    tree: Treeish,
    *,
    recursion: str = 'repository',
) -> Generator[GitTreeItem]:
    """Uses ``git ls-tree`` to report on a tree in a Git repository

    The ``path`` parameter identifies the Git repository to query.
    This directory need not be the root directory of the repository,
    but must be part of the repository. The ``treeish`` parameter
    identifiers the tree to report items for.

    If ``path`` is a subdirectory of a worktree (i.e., not the root of the
    worktree, or the location of a bare repository), the report is constrained
    to items underneath this path. In this case, ``treeish`` should only
    identify a revision, because the implementation has limited support for
    translating a subdirectory prefix into a query path independent ``treeish``
    to be reported with each yielded ``GitTreeItem``.  In this case, the
    effective treeish used for querying will be ``<treeish>:<subdir-prefix>``.
    The actual query is always performed against the root of the repository.

    The ``recursion`` parameter determines how subtrees are reported.
    By default (``repository``), all trees within the repository
    underneath ``treeish``) are reported, but not trees within a
    submodules. If ``none``, only direct children of ``treeish``
    are reported on.
    """
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

    for line in git_ls_tree(tree.repo.path, tree.treeish, *lstree_args):
        yield _get_tree_item(tree, line)


def _get_tree_item(tree: Treeish, spec: str) -> GitTreeItem:
    props, path = spec.split('\t', maxsplit=1)
    # 0::2 gets the first and third (last) item, effectively skippping the
    # type name (blob/tree etc.), we have the mode lookup for that, which
    # provides more detail
    mode, sha = props.split(' ')[0::2]
    return GitTreeItem(
        tree=tree,
        relpath=PurePosixPath(path),
        gitsha=sha,
        gittype=GitTreeItem.mode2type(mode),
    )
