from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from itertools import chain
from pathlib import (
    Path,
    PurePosixPath,
)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import (
        Generator,
        Iterable,
    )

from datasalad.gitpathspec import GitPathSpecs

from datalad_core.iter_collections.utils import git_ls_files
from datalad_core.repo import (
    GitTreeItem,
    GitTreeItemType,
    WorktreeDirectory,
    WorktreeItem,
)

# mapping of supported values of the `untracked` argument to `git ls-files`
# parameters
lsfiles_untracked_args = {
    None: ('--stage', '--cached'),
    'all': ('--stage', '--cached', '--exclude-standard', '--others'),
    'whole-dir': (
        '--stage',
        '--cached',
        '--exclude-standard',
        '--others',
        '--directory',
    ),
    'no-empty-dir': (
        '--stage',
        '--cached',
        '--exclude-standard',
        '--others',
        '--directory',
        '--no-empty-directory',
    ),
    'only': ('--exclude-standard', '--others'),
    'only-whole-dir': ('--exclude-standard', '--others', '--directory'),
    'only-no-empty-dir': (
        '--exclude-standard',
        '--others',
        '--directory',
        '--no-empty-directory',
    ),
}


def iter_gitworktree(
    path: Path | WorktreeDirectory,
    *,
    untracked: str | None = 'all',
    recursion: str = 'repository',
    pathspecs: list[str] | GitPathSpecs | None = None,
) -> Generator[WorktreeItem]:
    """Uses ``git ls-files`` to report on a work tree of a Git repository

    This iterator can be used to report on all tracked, and untracked content
    of a Git repository's work tree. This includes files that have been removed
    from the work tree (deleted), unless their removal has already been staged.

    For any tracked content, yielded items include type information and gitsha
    as last known to Git. This means that such reports reflect the last
    committed or staged content, not the state of a potential unstaged
    modification in the work tree.

    :class:`WorktreeItem` are yielded. Their ``gitsha`` and ``gittype``
    properties being ``None`` indicates untracked work tree content.

    .. note::
      The ``gitsha`` is not equivalent to a SHA1 hash of a file's content,
      but is the SHA-type blob identifier as reported and used by Git.

    Parameters
    ----------
    path: Path
      Path of a directory in a Git repository to report on. This directory
      need not be the root directory of the repository, but must be part of
      the repository's work tree.
    untracked: {'all', 'whole-dir', 'no-empty-dir', 'only', 'only-whole-dir', 'only-no-empty-dir'} or None, optional
      If not ``None``, also reports on untracked work tree content.
      ``all`` reports on any untracked file; ``whole-dir`` yields a single
      report for a directory that is entirely untracked, and not individual
      untracked files in it; ``no-empty-dir`` skips any reports on
      untracked empty directories. The modes starting with 'only' offer the
      same untracked content reporting styles, but only untracked and no
      tracked content is reported. For example, 'only' is the corresponding
      mode to 'all' with no tracked content being reported.
    recursion: {'submodules', 'repository', 'none'}, optional
      Behavior for recursion into subdirectories of ``path``. By default
      (``repository``), all directories within the repository are reported.
      This possibly includes untracked ones (see ``untracked``), but not
      directories within submodules. With ``submodules``, the full worktree
      is reported on with recursion into submodules. With ``none``,
      only direct children of ``path`` are reported on.
      For any worktree items in subdirectories of ``path`` only a single
      record for the containing immediate subdirectory ``path`` is yielded.
      For example, with 'path/subdir/file1' and 'path/subdir/file2' there
      will only be a single item with ``name='subdir'`` and
      ``type='directory'``.
    pathspecs: optional
      Patterns used to limit results to particular paths. Any pathspecs
      supported by Git can be used and are passed to the underlying ``git
      ls-files`` queries. Pathspecs are also supported for recursive reporting
      on submodules. In such a case, the results match those of individual
      queries with analog pathspecs on the respective submodules (Git itself
      does not support pathspecs for submodule-recursive operations).  For
      example, a ``submodule`` recursion with a pathspec ``*.jpg`` will yield
      reports on all JPG files in all submodules, even though a submodule path
      itself does not match ``*.jpg``.  On the other hand, a pathspec
      ``submoddir/*.jpg`` will only report on JPG files in the submodule at
      ``submoddir/``, but on all JPG files in that submodule.
      As of version 1.5, the pathspec support for submodule recursion is
      preliminary and results should be carefully investigated.
    """
    basedir = (
        path
        if isinstance(path, WorktreeDirectory)
        else WorktreeDirectory.from_path(path)
    )
    _pathspecs = GitPathSpecs(pathspecs)

    subm_to_process: list[WorktreeItem] = []

    # the helper takes care of talking to Git and doing recursion
    for item in _iter_gitworktree(
        basedir=basedir,
        untracked=untracked,
        # the helper cannot do submodule recursion, we do this outside,
        # so limit here
        recursion='repository' if recursion == 'submodules' else recursion,
        pathspecs=_pathspecs,
    ):
        # exclude non-submodules, or a submodule that was found at
        # the root path -- which would indicate that the submodule
        # itself it not around, only its record in the parent
        if (
            recursion == 'submodules'
            and item.gittype == GitTreeItemType.submodule
            and item.relpath != PurePosixPath('.')
        ):
            # mark for processing at the end
            subm_to_process.append(item)
            continue

        yield item

    # we may need to loop over the (remaining) submodules for two reasons:
    # - with pathspecs there is a chance that a given pathspec set did not
    #   match a submodule (directly) that could have content that matches a
    #   pathspec
    # - when we are looking for untracked content only, the code above
    #   (by definition) will not have found the submodules (because they are
    #   unconditionally tracked)
    yield from _report_items_from_submodules(
        chain(
            # submodules already found to need reporting on above
            subm_to_process,
            # and the (potentially) remaining ones, deduplication happening
            # via `processed_submodules`
            iter_submodules(
                path=path,
                pathspecs=_pathspecs,
                match_containing=True,
            )
            if recursion == 'submodules'
            and ((untracked and untracked.startswith('only')) or _pathspecs)
            else [],
        ),
        recursion=recursion,
        untracked=untracked,
        pathspecs=_pathspecs,
    )


def _report_items_from_submodules(
    subms: Iterable[WorktreeItem],
    *,
    recursion: str,
    untracked: str | None,
    pathspecs: GitPathSpecs,
) -> Generator[WorktreeItem]:
    processed_submodules: set[PurePosixPath] = set()
    for subm in subms:
        if subm.relpath in processed_submodules:
            # we dealt with that above already
            continue
        if not subm.path.exists():
            # no point in trying to list a submodule that is not around
            continue
        for item in iter_gitworktree(
            path=subm.path,
            recursion=recursion,
            untracked=untracked,
            # a previous implementation had the preprocessing
            # of the pathspec in a dedicated try-except in case
            # it cannot be translated. however, mih presently believes
            # that this is not necessary with this implementation, because
            # - we always have a pathspec here
            # - we only get here for pathspecs that matches the current
            # submodule already
            pathspecs=pathspecs.for_subdir(subm.relpath),
        ):
            yield replace(
                item,
                # make basedir uniform for all reports from the perspective
                # of the top-level query
                basedir=subm.basedir,
                relpath=subm.relpath / item.relpath,
            )
        processed_submodules.add(subm.relpath)


def _iter_gitworktree(
    basedir: WorktreeDirectory,
    *,
    untracked: str | None,
    recursion: str,
    pathspecs: GitPathSpecs,
) -> Generator[WorktreeItem, None, None]:
    """Internal helper for iter_gitworktree() tp support recursion"""

    # perform an implicit test of whether the `untracked` mode is known
    lsfiles_args = list(lsfiles_untracked_args[untracked])

    if pathspecs:
        lsfiles_args.extend(pathspecs.arglist())

    # helper to handle multi-stage reports by ls-files
    pending_item: WorktreeItem | None = None

    reported_dirs: set[PurePosixPath] = set()
    _single_dir = recursion == 'none'

    # we add a "fake" `None` record at the end to avoid a special
    # case for submitting the last pending item after the loop.
    # otherwise the context manager handling of the file pointer
    # would lead to lots of code duplication
    for line in chain(git_ls_files(basedir.path, *lsfiles_args), [None]):
        if pending_item is None and line is None:
            return

        # a bit ugly, but we need to account for the `None` record
        # that signals the final loop iteration
        item = None if line is None else _lsfiles_line2item(basedir, line)

        # yield any pending item, if the current record is not an
        # addendum of it
        if item is None or (pending_item and item.relpath != pending_item.relpath):
            if TYPE_CHECKING:
                # we already checked that not both items are None
                assert pending_item is not None
            # this is the last point where we can still withhold a report.
            # it is also the point where we can do this with minimal
            # impact on the rest of the logic.
            # so act on recursion setup now
            pending_item_path_parts = pending_item.relpath.parts
            if _single_dir and len(pending_item_path_parts) > 1:
                # this path is pointing inside a subdirectory of the
                # base directory -> ignore
                # reset pending_item here, decomplexifies the conditionals
                pending_item = item
                dir_path = PurePosixPath(pending_item_path_parts[0])
                if dir_path in reported_dirs:
                    # we only yield each containing dir once, and only once
                    continue
                yield WorktreeItem(
                    basedir=basedir,
                    relpath=dir_path,
                    gittype=GitTreeItemType.directory,
                    gitsha=None,
                )
                reported_dirs.add(dir_path)
                continue

            # report on a pending item, this is not a "higher-stage"
            # report by ls-files
            yield pending_item

        # do not yield immediately, wait for a possible higher-stage
        # report in the next loop iteration
        pending_item = item


def iter_submodules(
    path: Path | WorktreeDirectory,
    *,
    pathspecs: list[str] | GitPathSpecs | None = None,
    match_containing: bool = False,
) -> Generator[WorktreeItem]:
    """Given a path, report all submodules of a repository worktree underneath

    With ``match_containing`` set to the default ``False``, this is merely a
    convenience wrapper around ``iter_gitworktree()`` that selectively reports
    on submodules. With ``match_containing=True`` and ``pathspecs`` given, the
    yielded items corresponding to submodules where the given ``pathsspecs``
    *could* match content. This includes submodules that are not available
    locally, because no actual matching of pathspecs to submodule content is
    performed -- only an evaluation of the submodule item itself.
    """
    basedir = (
        path
        if isinstance(path, WorktreeDirectory)
        else WorktreeDirectory.from_path(path)
    )
    _pathspecs = GitPathSpecs(pathspecs)
    if not _pathspecs:
        # force flag to be sensible to simplify internal logic
        match_containing = False

    for item in iter_gitworktree(
        basedir,
        untracked=None,
        recursion='repository',
        # if we want to match submodules that contain pathspecs matches
        # we cannot give the job to Git, it won't report anything,
        # but we need to match manually below
        pathspecs=None if match_containing else _pathspecs,
    ):
        if (
            # exclude non-submodules, or a submodule that was found at
            # the root path -- which would indicate that the submodule
            # itself it not around, only its record in the parent
            item.gittype == GitTreeItemType.submodule
            and item.relpath != PurePosixPath('.')
            # does any pathspec match the "inside" of the current submodule's
            # path
            and (not match_containing or _pathspecs.any_match_subdir(item.relpath))
        ):
            yield item


def _lsfiles_line2item(basedir: WorktreeDirectory, line: str) -> WorktreeItem:
    items = line.split('\t', maxsplit=1)
    # check if we cannot possibly have a 'staged' report with mode and gitsha
    if len(items) < 2:  # noqa: PLR2004
        # early exit, we have nothing but the path (untracked)
        return WorktreeItem(
            basedir=basedir,
            # not known to Git, but Git always reports POSIX
            relpath=PurePosixPath(line),
        )

    props = items[0].split(' ')
    if len(props) != 3:  # noqa: PLR2004
        # early exit again, we have nothing but the path (untracked)
        return WorktreeItem(
            basedir=basedir,
            # not known to Git, but Git always reports POSIX
            relpath=PurePosixPath(items[1]),
        )

    return WorktreeItem(
        basedir=basedir,
        # again Git reports always in POSIX
        relpath=PurePosixPath(items[1]),
        gitsha=props[1],
        gittype=GitTreeItem.mode2type(props[0]) if props[0] else None,
    )
