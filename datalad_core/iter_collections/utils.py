from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

from datasalad.itertools import (
    decode_bytes,
    itemize,
)

from datalad_core.runners import iter_git_subproc


def iter_gitcmd_zlines(
    path: Path,
    cmd: str,
    *args: str,
) -> Iterator[str]:
    """Run ``git <cmd>`` at a given ``path`` and with ``args``

    An unconditional ``-z`` argument is used to get zero-byte separation
    of output items, internally. A generator is returned that yields ``str``
    type values corresponding to these items.
    """
    with iter_git_subproc(
        [
            cmd,
            # we rely on zero-byte splitting below
            '-z',
            # otherwise take whatever is coming in
            *args,
        ],
        cwd=path,
    ) as r:
        yield from itemize(
            decode_bytes(r, backslash_replace=True),
            sep='\0',
            keep_ends=False,
        )


def git_ls_files(path: Path, *args: str) -> Iterator[str]:
    """Run ``git ls-files`` at a given ``path`` and with ``args``"""
    return iter_gitcmd_zlines(path, 'ls-files', *args)


def git_ls_tree(path: Path, *args) -> Iterator[str]:
    """Run ``git ls-tree`` at a given ``path`` and with ``args``"""
    return iter_gitcmd_zlines(path, 'ls-tree', *args)


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


# TODO: Could be `StrEnum`, came with PY3.11
class GitDiffStatus(Enum):
    """Enumeration of statuses for diff items"""

    addition = 'addition'
    copy = 'copy'
    deletion = 'deletion'
    modification = 'modification'
    rename = 'rename'
    typechange = 'typechange'
    unmerged = 'unmerged'
    unknown = 'unknown'
    # this is a local addition and not defined by git
    # AKA "untracked"
    other = 'other'


git_diffstatus_map = {
    'A': GitDiffStatus.addition,
    'C': GitDiffStatus.copy,
    'D': GitDiffStatus.deletion,
    'M': GitDiffStatus.modification,
    'R': GitDiffStatus.rename,
    'T': GitDiffStatus.typechange,
    'U': GitDiffStatus.unmerged,
    'X': GitDiffStatus.unknown,
    'O': GitDiffStatus.other,
}


# TODO: Could be `StrEnum`, came with PY3.11
class GitContainerModificationType(Enum):
    new_commits = 'new commits'
    untracked_content = 'untracked content'
    modified_content = 'modified content'
