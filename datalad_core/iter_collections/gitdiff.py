from __future__ import annotations

from contextlib import suppress
from dataclasses import (
    dataclass,
    replace,
)
from itertools import chain
from pathlib import (
    Path,
    PurePosixPath,
)
from typing import (
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    from collections.abc import Generator


from datasalad.gitpathspec import GitPathSpecs

from datalad_core.consts import PRE_INIT_COMMIT_SHA
from datalad_core.iter_collections.gittree import (
    GitTreeItem,
)
from datalad_core.iter_collections.utils import (
    GitContainerModificationType,
    GitDiffStatus,
    GitTreeItemType,
    git_diffstatus_map,
    git_mode_type_map,
    iter_gitcmd_zlines,
)
from datalad_core.runners import (
    CommandError,
    call_git,
    call_git_oneline,
)


@dataclass(frozen=True)
class GitDiffItem(GitTreeItem):
    """``GitTreeItem`` with "previous" property values given a state comparison"""

    prev_relpath: PurePosixPath | None = None
    prev_gitsha: str | None = None
    prev_gittype: GitTreeItemType | None = None

    status: GitDiffStatus | None = None
    percentage: int | None = None
    """This is the percentage of similarity for copy-status and
    rename-status diff items, and the percentage of dissimilarity
    for modifications."""
    modification_types: tuple[GitContainerModificationType, ...] | None = None
    """Qualifiers for modification types of container-type
    items (directories, submodules)."""


def iter_gitdiff(
    path: Path,
    from_treeish: str | None,
    to_treeish: str | None,
    *,
    recursion: str = 'repository',
    find_renames: int | None = None,
    find_copies: int | None = None,
    pathspecs: list[str] | GitPathSpecs | None = None,
) -> Generator[GitDiffItem, None, None]:
    """Report differences between Git tree-ishes or tracked worktree content

    This function is a wrapper around the Git command ``diff-tree`` and
    ``diff-index``. Therefore most semantics also apply here.

    The main difference with respect to the Git commands are: 1) uniform
    support for non-recursive, single tree reporting (no subtrees); and
    2) support for submodule recursion.

    Notes on 'none' recursion mode

    When comparing to the worktree, ``git diff-index`` always reports on
    subdirectories. For homogeneity with the report on a committed tree,
    a non-recursive mode emulation is implemented. It compresses all reports
    from a direct subdirectory into a single report on that subdirectory.
    The ``gitsha`` of that directory item will always be ``None``. Moreover,
    no type or typechange inspection, or further filesystem queries are
    performed. Therefore, ``prev_gittype`` will always be ``None``, and
    any change other than the addition of the directory will be labeled
    as a ``GitDiffStatus.modification``.

    Parameters
    ----------
    path: Path
      Path of a directory in a Git repository to report on. This directory
      need not be the root directory of the repository, but must be part of
      the repository. If the directory is not the root directory of a
      non-bare repository, the iterator is constrained to items underneath
      that directory.
    from_treeish: str or None
      Git "tree-ish" that defines the comparison reference. If ``None``,
      ``to_treeeish`` must not be ``None`` (see its documentation for
      details).
    to_treeish:
      Git "tree-ish" that defines the comparison target. If ``None``,
      ``from_treeish`` must not be ``None``, and that tree-ish will be
      compared against the worktree. (see its documentation for
      details). If ``from_treeish`` is ``None``, the given tree-ish is
      compared to its immediate parents (see ``git diff-tree`` documentation
      for details).
    recursion: {'repository', 'submodules', 'no'}, optional
      Behavior for recursion into subtrees. By default (``repository``),
      all trees within the repository underneath ``path``) are reported,
      but no tree within submodules. With ``submodules``, recursion includes
      any submodule that is present. If ``no``, only direct children
      are reported on.
    find_renames: int, optional
      If given, this defines the similarity threshold for detecting renames
      (see ``git diff-{index,tree} --find-renames``). By default, no rename
      detection is done and reported items never have the ``rename`` status.
      Instead, a renames would be reported as a deletion and an addition.
    find_copied: int, optional
      If given, this defines the similarity threshold for detecting copies
      (see ``git diff-{index,tree} --find-copies``). By default, no copy
      detection is done and reported items never have the ``copy`` status.
      Instead, a copy would be reported as addition.
      This option always implies the use of the ``--find-copies-harder``
      Git option that enables reporting of copy sources, even when they
      have not been modified in the same change. This is a very expensive
      operation for large projects, so use it with caution.
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

    Yields
    ------
    :class:`GitDiffItem`
      The ``name`` and ``prev_name`` attributes of an item are a ``str`` with
      the corresponding (relative) path, as reported by Git
      (in POSIX conventions).
    """
    if recursion not in {
        'none',
        'none-ignore-submodules',
        'none-ignore-submodules-dirty',
        'repository',
        'repository-ignore-submodules',
        'repository-ignore-submodules-dirty',
        'submodules',
        'submodules-and-yield',
    }:
        msg = f'unknown recursion mode {recursion!r}'
        raise ValueError(msg)
    # we force-convert to Path to give us the piece of mind we want.
    # The docs already ask for that, but it is easy to
    # forget/ignore and leads to non-obvious errors. Running this once is
    # a cheap safety net
    path = Path(path)
    _pathspecs = GitPathSpecs(pathspecs)
    processed_submodules: set[PurePosixPath] = set()

    for item in _iter_gitdiff(
        path=path,
        from_treeish=from_treeish,
        to_treeish=to_treeish,
        recursion=recursion,
        find_renames=find_renames,
        find_copies=find_copies,
        pathspecs=_pathspecs,
    ):
        # exclude non-submodules, or a submodule that was found at
        # the root path -- which would indicate that the submodule
        # itself it not around, only its record in the parent
        if (
            recursion.startswith('submodules')
            and item.gittype == GitTreeItemType.submodule
            and item.relpath != PurePosixPath('.')
        ):
            # mark as processed immediately, independent of whether anything
            # need to be reported
            processed_submodules.add(item.relpath)
        yield item

    # we may need to loop over the (remaining) submodules, because
    # with pathspecs there is a chance that a given pathspec set did not
    # match a submodule (directly) that could have content that matches a
    # pathspec
    if not (recursion.startswith('submodules') and _pathspecs):
        return

    for item in _iter_gitdiff(
        path=path,
        from_treeish=from_treeish,
        to_treeish=to_treeish,
        # no need to double-recurse, we just need to discover all
        # submodules in the diff unconstrained by pathspecs
        # we only need to look at the recorded commits to get submodule
        # reports
        recursion='repository-ignore-submodule-dirty',
        find_renames=None,
        find_copies=None,
        pathspecs=GitPathSpecs(None),
    ):
        if (
            item.gittype != GitTreeItemType.submodule
            or item.relpath in processed_submodules
        ):
            # not a submodule or already reported on
            continue

        yield from _yield_from_submodule(
            basepath=path,
            subm=item,
            to_treeish=to_treeish,
            recursion=recursion,
            find_renames=find_renames,
            find_copies=find_copies,
            pathspecs=_pathspecs,
        )


def _iter_gitdiff(
    path: Path,
    from_treeish: str | None,
    to_treeish: str | None,
    *,
    recursion: str,
    find_renames: int | None,
    find_copies: int | None,
    pathspecs: GitPathSpecs,
) -> Generator[GitDiffItem, None, None]:
    cmd, cmd_args = _build_cmd(
        from_treeish=from_treeish,
        to_treeish=to_treeish,
        recursion=recursion,
        find_renames=find_renames,
        find_copies=find_copies,
        pathspecs=pathspecs,
    )

    if cmd == 'diff-index':
        # when we compare to the index, we need a refresh run to not have
        # something like plain mtime changes trigger modification reports
        # https://github.com/datalad/datalad-next/issues/639
        call_git(
            [
                'update-index',
                # must come first, we recurse ourselves
                '--ignore-submodules',
                # we want to continue the refresh when the index need updating
                '-q',
                '--refresh',
            ],
            cwd=path,
        )

    # when do we need to condense subdir reports into a single dir-report
    reported_dirs: set[str] = set()
    _single_dir = (cmd == 'diff-index') and recursion.startswith('none')
    # diff-tree reports the compared tree when no from is given, we need
    # to skip that output below
    skip_first = (cmd == 'diff-tree') and from_treeish is None
    pending_props = None
    for line in chain(iter_gitcmd_zlines(path, cmd, *cmd_args), [None]):
        if skip_first:
            skip_first = False
            continue
        if pending_props:
            if line is not None:
                pending_props.append(line)
                if pending_props[4][0] in ('C', 'R'):
                    # for copies and renames we expect a second path.
                    # unless we are already on the end marker, in which
                    # case this is already the missing
                    continue
            yield from _yield_diff_item(
                cwd=path,
                single_dir=_single_dir,
                spec=pending_props,
                reported_dirs=reported_dirs,
                from_treeish=from_treeish,
                to_treeish=to_treeish,
                recursion=recursion,
                find_renames=find_renames,
                find_copies=find_copies,
                pathspecs=pathspecs,
            )
            pending_props = None
        elif line is None:
            # this is the end marker, nothing to do
            pass
        elif line.startswith(':'):
            pending_props = line[1:].split(' ')
        else:  # pragma: no cover
            msg = 'we should not get here, unexpected diff output'
            raise RuntimeError(msg)


def _build_cmd(
    *,
    from_treeish: str | None,
    to_treeish: str | None,
    recursion: str,
    find_renames: int | None,
    find_copies: int | None,
    pathspecs: GitPathSpecs,
) -> tuple[str, list[str]]:
    # from   : to   : description
    # ---------------------------
    # HEAD   : None : compare to worktree, not with the index (diff-index)
    # HEAD~2 : HEAD : compare trees (diff-tree)
    # None   : HEAD~2 : compare tree with its parents (diff-tree)
    # None   : None : exception

    common_args: list[str] = [
        '--no-rename-empty',
        # ignore changes above CWD
        '--relative',
        '--raw',
    ]
    if find_renames is not None:
        common_args.append(f'--find-renames={find_renames}%')
    if find_copies is not None:
        common_args.append(f'--find-copies={find_copies}%')
        # if someone wants to look for copies, we actually look
        # for copies. This is expensive, but IMHO is the one
        # thing that makes this useful
        # TODO: possibly we only want to enable this when
        # find_copies==100 (exact copies), based on the assumption
        # that this is cheaper than reading all file content.
        # but if that is actually true remains to be tested
        common_args.append('--find-copies-harder')

    # entrypoint verifies that only valid modes bring us here
    if recursion.endswith('-ignore-submodules'):
        common_args.append('--ignore-submodules=all')
    elif recursion.endswith('-ignore-submodules-dirty'):
        common_args.append('--ignore-submodules=dirty')
    else:  # full mode
        common_args.append('--ignore-submodules=none')

    if from_treeish is None and to_treeish is None:
        msg = 'either `from_treeish` or `to_treeish` must not be None'
        raise ValueError(msg)
    if to_treeish is None:
        if TYPE_CHECKING:
            assert from_treeish is not None
        cmd = 'diff-index'
        cmd_args = [*common_args, from_treeish]
    else:
        # diff NOT against the working tree
        cmd = 'diff-tree'
        cmd_args = [*common_args]
        if recursion.startswith(('repository', 'submodules')):
            cmd_args.append('-r')
        if from_treeish is None:
            cmd_args.append(to_treeish)
        else:
            # two tree-ishes given
            cmd_args.extend((from_treeish, to_treeish))

    # add disambiguation marker for pathspec.
    # even if we do not pass any, we get simpler error messages from Git
    cmd_args.append('--')

    cmd_args.extend(pathspecs.arglist())
    return cmd, cmd_args


def _get_diff_item(spec: list[str]) -> GitDiffItem:
    # this helper decodes the git-diff-tree/index raw output format to
    # a GitDiffItem
    non_rename_spec_length = 6

    prev_gittype = git_mode_type_map.get(spec[0], None)
    gittype = git_mode_type_map.get(spec[1], None)

    prev_gitsha = None if spec[2] == 40 * '0' else spec[2]
    gitsha = None if spec[3] == 40 * '0' else spec[3]

    # first char is status code
    status = git_diffstatus_map[spec[4][0]]
    percentage: int | None = None
    if len(spec[4]) > 1:
        percentage = int(spec[4][1:])

    modification_types: tuple[GitContainerModificationType, ...] | None = None
    if status == GitDiffStatus.addition:
        # this is an addition, we want `relpath` in the right place
        relpath = PurePosixPath(spec[5])
        prev_relpath = None
        if gitsha is None:
            modification_types = (GitContainerModificationType.modified_content,)
    else:
        prev_relpath = PurePosixPath(spec[5])
        relpath = PurePosixPath(
            spec[6] if len(spec) > non_rename_spec_length else spec[5]
        )

    return GitDiffItem(
        relpath=relpath,
        prev_relpath=prev_relpath,
        gitsha=gitsha,
        prev_gitsha=prev_gitsha,
        gittype=gittype,
        prev_gittype=prev_gittype,
        status=status,
        percentage=percentage,
        modification_types=modification_types,
    )


def _yield_diff_item(
    *,
    cwd: Path,
    recursion: str,
    from_treeish: str | None,
    to_treeish: str | None,
    spec: list,
    single_dir: bool,
    reported_dirs: set,
    find_renames: int | None,
    find_copies: int | None,
    pathspecs: GitPathSpecs,
) -> Generator[GitDiffItem, None, None]:
    item = _get_diff_item(spec)

    # the number of path parts that indicate an item inside a subdir
    min_subdir_path_parts = 2

    if single_dir:
        if TYPE_CHECKING:
            # we can only get here when diff-index ran, in which case
            # to_treeish was None and consequently from_treeish can never
            # be None at this point
            assert from_treeish is not None
        # handle the special case of reporting only on the 1st-level
        # containing directory of an item.
        relpath = item.relpath or item.prev_relpath
        if TYPE_CHECKING:
            # we cannot have items that have no relpath whatsoever
            assert relpath is not None
        # we decide on mangling the actual report to be on the containing
        # directory only, or to withhold it entirely
        if len(relpath.parts) < min_subdir_path_parts:
            # nothing in a subdirectory
            yield item
            return
        dname = relpath.parts[0]
        if dname in reported_dirs:
            # nothing else todo, we already reported
            return

        reported_dirs.add(dname)
        yield _mangle_item_for_singledir(
            PurePosixPath(dname),
            from_treeish,
            cwd,
        )
        return

    if item.gittype != GitTreeItemType.submodule:
        # any non-submodule item can be yielded now and we are done here
        yield item
        return

    # this is about a present submodule.
    # sadly, we cannot give details for modification types other than addition.
    # depending on --ignore-submodules a range of situations
    # could be the case
    if item.status == GitDiffStatus.modification and item.gitsha is None:
        # in 'git diff-index' speak the submodule is "out-of-sync" with
        # the index: this happens when there are new commits
        item = replace(
            item,
            modification_types=(
                *(item.modification_types or ()),
                GitContainerModificationType.new_commits,
            ),
        )

    if not recursion.startswith('submodules'):
        # no submodule recursion, we can yield this submodule item
        # directly
        yield item
        return

    if recursion == 'submodules-and-yield':
        yield item

    yield from _yield_from_submodule(
        basepath=cwd,
        subm=item,
        to_treeish=to_treeish,
        recursion=recursion,
        find_renames=find_renames,
        find_copies=find_copies,
        pathspecs=pathspecs,
    )


def _yield_from_submodule(
    *,
    basepath: Path,
    subm: GitDiffItem,
    to_treeish: str | None,
    recursion: str,
    find_renames: int | None,
    find_copies: int | None,
    pathspecs: GitPathSpecs,
) -> Generator[GitDiffItem, None, None]:
    # I believe we need no protection against absent submodules.
    # The only way they can appear here is a reported modification.
    # The only modification that is possible with an absent submodule
    # is a deletion. And that would cause the item.gittype to be None
    # -- a condition that is caught above
    subm_relpath = PurePosixPath(subm.relpath)
    subm_pathspecs = pathspecs
    if pathspecs:
        # we only get here, when the submodule itself matched.
        # mih cannot think of a way where none of any pathspecs
        # would not translate to ':' at least.
        # try:
        # recode pathspecs to match the submodule scope
        subm_pathspecs = pathspecs.for_subdir(subm_relpath)
        # except ValueError:
        #    # not a single pathspec could be translated, there is
        #    # no chance for a match, we can stop here
        #    return
    for i in iter_gitdiff(
        basepath / subm_relpath,
        # we never want to pass None here
        # if `prev_gitsha` is None, it means that the
        # submodule record is new, and we want its full
        # content reported. Passing None, however,
        # would only report the change to the current
        # state.
        from_treeish=subm.prev_gitsha or PRE_INIT_COMMIT_SHA,
        # when comparing the parent to the worktree, we
        # also want to compare any children to the worktree
        to_treeish=None if to_treeish is None else subm.gitsha,
        # pass on the common args
        recursion=recursion,
        find_renames=find_renames,
        find_copies=find_copies,
        pathspecs=subm_pathspecs,
    ):
        # prepend any item relpath with the parent items
        # relpath
        yield replace(
            i,
            relpath=None if i.relpath is None else subm.relpath / i.relpath,
            prev_relpath=None
            if i.prev_relpath is None
            else subm.relpath / i.prev_relpath,
        )


def _mangle_item_for_singledir(
    dname: PurePosixPath,
    from_treeish: str,
    cwd: Path,
) -> GitDiffItem:
    # at this point we have a change report on subdirectory content
    # we only get here when comparing `from_treeish` to the worktree.
    prev_gitsha = None
    # on error `dname` is not known in `from_treeish`
    with suppress(CommandError):
        prev_gitsha = call_git_oneline(
            ['rev-parse', '-q', f'{from_treeish}:./{dname}'],
            cwd=cwd,
        )

    return GitDiffItem(
        relpath=dname,
        # if we have a previous gitsha, we know that the relpath was valid in
        # `from_treeish` too
        prev_relpath=dname if prev_gitsha else None,
        # non-committed change -> no SHA (this ignored the index,
        # like we do elsewhere too)
        gitsha=None,
        prev_gitsha=prev_gitsha,
        # this is only ever about a directory
        gittype=GitTreeItemType.directory,
        # it would require more calls to figure out the mode and infer
        # a possible type change. For now, we do not go there
        prev_gittype=None,
        status=GitDiffStatus.modification
        if prev_gitsha
        # the was nothing with this relpath in `from_treeish`, but now
        # it exists. We compare to the worktree, but not any untracked
        # content -- this means that we likely compare across multiple
        # states and the directory become tracked after `from_treeish`.
        # let's call it an addition
        else GitDiffStatus.addition,
    )
