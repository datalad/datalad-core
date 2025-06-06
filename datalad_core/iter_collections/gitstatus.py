"""Report on the status of the worktree

The main functionality is provided by the :func:`iter_gitstatus` function.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator, Iterator

from datalad_core.consts import PRE_INIT_COMMIT_SHA
from datalad_core.iter_collections.gitdiff import (
    GitContainerModificationType,
    GitDiffItem,
    GitDiffStatus,
    iter_gitdiff,
)
from datalad_core.iter_collections.gitworktree import (
    GitTreeItemType,
    GitWorktreeItem,
    iter_gitworktree,
    iter_submodules,
)
from datalad_core.runners import (
    CommandError,
    call_git_lines,
)

# map untracked modes given to iter_gitstatus() to those that need to be
# passed to iter_gitworktree() for getting untracked content only
_untracked_mode_map = {
    'all': 'only',
    'whole-dir': 'only-whole-dir',
    'no-empty-dir': 'only-no-empty-dir',
}


def iter_gitstatus(
    path: Path,
    *,
    untracked: str | None = 'all',
    recursion: str = 'repository',
    head: str | None = None,
) -> Generator[GitDiffItem, None, None]:
    """
    When ``head`` is ``None`` (default) the reference commit for the status
    evaluation is determined in the following way: For a git-annex repository
    in adjusted mode, the HEAD commit of the corresponding (non-adjusted)
    branch is used. Otherwise, and also for any repository not managed by
    git-annex or not in adjusted mode, the HEAD commit of the worktree is
    used. For an unborn branch (no commit), the comparison is done against
    an empty tree.


    Recursion mode 'none'

    This mode limits the reporting to immediate directory items of a given
    path. This mode is not necessarily faster than a 'repository' recursion.
    Its primary purpose is the ability to deliver a collapsed report in that
    subdirectories are treated similar to submodules -- as containers that
    maybe have modified or untracked content.

    Parameters
    ----------
    path: Path
      Path of a directory in a Git repository to report on. This directory
      need not be the root directory of the repository, but must be part of
      the repository. If the directory is not the root directory of a
      non-bare repository, the iterator is constrained to items underneath
      that directory.
    untracked: {'all', 'whole-dir', 'no-empty-dir'} or None, optional
      If not ``None``, also reports on untracked work tree content.
      ``all`` reports on any untracked file; ``whole-dir`` yields a single
      report for a directory that is entirely untracked, and not individual
      untracked files in it; ``no-empty-dir`` skips any reports on
      untracked empty directories. Also see ``eval_submodule_state`` for
      how this parameter is applied in submodule recursion.
    recursion: {'none', 'repository', 'submodules', 'monolithic'}, optional
      Behavior for recursion into subtrees. By default (``repository``),
      all trees within the repository underneath ``path``) are reported,
      but no tree within submodules. With ``submodules``, recursion includes
      any submodule that is present. If ``no``, only direct children
      are reported on.

    .. note::

       The implementation requires `git rev-parse --path-format=relative`
       that was introduced with Git v2.31.
    """
    # TODO: check untracked and recursion mode values
    path = Path(path)

    if head is None:
        wt_head, corresponding_head = get_worktree_head(path)
        # by default, we always compare against any
        # existing corresponding_head. This makes the status communicate
        # anything that has not made it into the corresponding branch yet.
        # This is also similar to what is being done for submodules with
        # monolithic recursion
        head = corresponding_head or wt_head
    if head is None:
        # no commit at all -> compare to an empty repo.
        head = PRE_INIT_COMMIT_SHA

    if recursion.startswith('none'):
        gen_items = _yield_dir_items
    elif recursion.startswith('repository'):
        gen_items = _yield_repo_items
    elif recursion.startswith(('submodules', 'monolithic')):
        gen_items = _yield_hierarchy_items
    else:
        msg = f'unknown recursion type {recursion!r}'
        raise ValueError(msg)

    # and now yield change records. however, filter out any item that does
    # not indicate an actual modification. we do this centrally at the top,
    # because it avoids a ton of conditionals in the internal implementations,
    # and is more gentle for a developer brain
    yield from filter(
        lambda item: item.status is not None,
        gen_items(
            head=head,
            path=path,
            untracked=untracked,
            recursion=recursion,
        ),
    )


#
# status generators for each mode
#


# potential container items in a directory that need content
# investigation
container_types = (
    GitTreeItemType.directory,
    GitTreeItemType.submodule,
)


def _yield_dir_items(
    *,
    head: str,
    path: Path,
    untracked: str | None,
    recursion: str,
) -> Iterator[GitDiffItem]:
    dir_items = (
        # no need to look at anything other than the diff report
        {}
        if untracked is None
        # gather all directory items upfront, we subtract the ones reported
        # modified later and lastly yield all untracked content from them
        else {
            item.relpath: item
            for item in iter_gitworktree(
                path,
                # there is no recursion, avoid wasting cycles on listing
                # individual files in subdirectories
                untracked='whole-dir' if untracked == 'all' else untracked,
                recursion='none',
            )
        }
    )
    # diff constrained to direct children
    for item in iter_gitdiff(
        path,
        from_treeish=head,
        # to the worktree
        to_treeish=None,
        # TODO: trim scope like in repo_items
        recursion=recursion,
    ):
        if item.status == GitDiffStatus.deletion or item.gittype not in container_types:
            yield item
            continue

        # when we continue to the next iteration, we will have dealt with this
        # item completely
        dir_items.pop(item.relpath, None)

        if item.gittype == GitTreeItemType.submodule:
            # issue standard submodule container report
            yield _eval_submodule(path, item, recursion)
            continue

        # this is on a directory. if it appears here, it has
        # modified content
        dir_path = path / item.relpath
        if not dir_path.exists():
            # this directory is gone entirely
            yield replace(
                item,
                status=GitDiffStatus.deletion,
                modification_types=None,
            )
            continue

        # some other modification
        modification_types = [GitContainerModificationType.modified_content]
        if untracked is not None and _path_has_untracked(dir_path):
            modification_types.append(GitContainerModificationType.untracked_content)
        yield replace(
            item,
            modification_types=(
                *(item.modification_types or ()),
                *modification_types,
            ),
        )

    if untracked is None:
        return

    # yield anything untracked, and inspect remaining containers
    for dir_item in dir_items.values():
        di = _eval_dir_item(path, dir_item, recursion)
        if di is None:
            continue
        yield di


def _eval_dir_item(
    path: Path,
    dir_item: GitWorktreeItem,
    recursion: str,
) -> GitDiffItem | None:
    if dir_item.gitsha is None and dir_item.gittype is None:
        # this is untracked
        return GitDiffItem(
            relpath=dir_item.relpath,
            status=GitDiffStatus.other,
        )

    if dir_item.gittype not in container_types:
        return None

    # none of these containers has any modification other than
    # possibly untracked content
    item = GitDiffItem(
        relpath=dir_item.relpath,
        # this submodule has not been detected as modified
        # per-commit, assign reported gitsha to pre and post
        # state
        gitsha=dir_item.gitsha,
        prev_gitsha=dir_item.gitsha,
        gittype=dir_item.gittype,
        # TODO: others?
    )

    if item.gittype == GitTreeItemType.submodule:
        # issue standard submodule container report
        return _eval_submodule(path, item, recursion)

    # this is a plain directory, only mention it when it has untracked
    # content
    # TODO: can it even happen that we get here for a directory that
    # does not even have untracked content? An empty directory? Do we need
    # to behavior according to ``untracked`` somehow more than we do
    # already?
    if _path_has_untracked(path / dir_item.path):
        return replace(
            item,
            status=GitDiffStatus.modification,
            modification_types=(GitContainerModificationType.untracked_content,),
        )

    return None


def _yield_repo_items(
    *,
    head: str | None,
    path: Path,
    untracked: str | None,
    recursion: str,
) -> Generator[GitDiffItem, None, None]:
    """Report status items for a single/whole repsoitory"""
    present_submodules = {item.relpath: item for item in iter_submodules(path)}
    # start with a repository-contrained diff against the worktree
    for item in iter_gitdiff(
        path,
        from_treeish=head,
        # to the worktree
        to_treeish=None,
        # we should be able to go cheaper with the submodule evaluation here.
        # We need to redo some check for adjusted mode, and other cases anyways
        recursion='repository-ignore-submodules-dirty'
        if recursion != 'repository-ignore-submodules'
        else recursion,
    ):
        # immediately investigate any submodules that are already
        # reported modified by Git
        if item.gittype == GitTreeItemType.submodule:
            yield _eval_submodule(path, item, recursion)
            # we dealt with this submodule
            present_submodules.pop(item.relpath, None)
        else:
            yield item

    # we are not generating a recursive report for submodules, hence
    # we need to look at ALL submodules for untracked content
    # `or {}` for the case where we got no submodules, which happens
    # with `recursion == '...-ignore-submodules'`
    yield from (
        _eval_submodule(
            path,
            GitDiffItem(
                relpath=subm_item.relpath,
                # this submodule has not been detected as modified
                # per-commit, assign reported gitsha to pre and post
                # state
                gitsha=subm_item.gitsha,
                prev_gitsha=subm_item.gitsha,
                gittype=subm_item.gittype,
                # TODO: others?
            ),
            # TODO: possibly trim recursion
            recursion,
        )
        # none of these submodules has any modification other than
        # possibly untracked content
        for subm_item in (present_submodules or {}).values()
    )

    if untracked is None:
        return

    # lastly untracked files of this repo
    yield from (
        GitDiffItem(
            relpath=untracked_item.relpath,
            status=GitDiffStatus.other,
            gittype=untracked_item.gittype,
        )
        for untracked_item in iter_gitworktree(
            path=path,
            untracked=_untracked_mode_map[untracked],
            recursion='repository',
        )
    )


def _yield_hierarchy_items(
    *,
    head: str | None,
    path: Path,
    untracked: str | None,
    recursion: str,
) -> Generator[GitDiffItem, None, None]:
    for item in _yield_repo_items(
        head=head,
        path=path,
        untracked=untracked,
        # TODO: do we need to adjust the eval mode here for the diff recmodes?
        recursion=recursion,
    ):
        # there is nothing else to do for any non-submodule item
        if item.status is None or item.gittype != GitTreeItemType.submodule:
            yield item
            continue

        if (
            # because this need not cover all possible changes with respect
            # to the parent repository, we yield an item on the submodule
            # itself
            recursion.startswith('submodules')
            or recursion == 'monolithic'
            and (
                # this is a submodule that is either entriely new (added),
                # or it has new commits compared to
                # its state in the parent dataset. We need to yield this
                # item, even if nothing else is modified, because otherwise
                # this (unsafed) changed would go unnoticed
                # https://github.com/datalad/datalad-next/issues/645
                item.modification_types is None
                or GitContainerModificationType.new_commits in item.modification_types
            )
        ):
            yield item

        # we get to see any submodule item passing through here, and can simply
        # call this function again for a subpath

        # submodule recursion, we need the path of the worktree of the
        # submodule within the parent
        sm_path = path / item.relpath
        sm_head = (
            # in 'submodules' recursion mode, we run the submodule status
            # against its own worktree head
            get_worktree_head(sm_path)[0]
            if recursion.startswith('submodules')
            # in 'monolithic' mode we determine the change of the submodule
            # with respect to the recorded state in the parent. This is either
            # the current gitsha, or (if git detected a committed
            # modification) the previous sha. This way, any further report
            # on changes a comprehensive from the point of view of the parent
            # repository, hence no submodule item is emitted
            else (item.gitsha or item.prev_gitsha)
        )

        yield from (
            replace(i, relpath=item.relpath / i.relpath)
            for i in _yield_hierarchy_items(
                head=sm_head,
                path=sm_path,
                untracked=untracked,
                # TODO: here we could implement handling for a recursion-depth
                # limit
                recursion=recursion,
            )
        )


#
# Helpers
#


def _path_has_untracked(path: Path) -> bool:
    """Recursively check for any untracked content (except empty dirs)"""
    if not path.exists():
        # cannot possibly have untracked
        return False
    # fast exit on the first detection
    # only after we saw everything we can say there is nothing
    return any(
        iter_gitworktree(
            path=path,
            untracked='only-no-empty-dir',
            recursion='submodules',
        )
    )


def _get_submod_worktree_head(path: Path) -> tuple[bool, str | None, bool]:
    """Returns (submodule exists, SHA | None, adjusted)"""
    try:
        head, corresponding_head = get_worktree_head(path)
    except ValueError:
        return False, None, False

    adjusted = corresponding_head is not None
    if adjusted:
        # this is a git-annex adjusted branch. do the comparison against
        # its basis. it is not meaningful to track the managed branch in
        # a superdataset
        head = corresponding_head
    if head is None:
        # a submodule always has a HEAD commit by definition, because
        # this is the only thing that defines it in the parent repo
        msg = 'function must not be used on a non-submodule'
        raise RuntimeError(msg)
    res = call_git_lines(
        ['rev-parse', '--path-format=relative', '--show-toplevel', head],
        cwd=path,
    )
    expected_args = 2
    if len(res) != expected_args:  # pragma: no cover
        msg = 'git rev-parse did not return the expected number of results'
        raise RuntimeError(msg)
    if res[0].startswith('..'):
        # this is not a report on a submodule at this location
        return False, None, adjusted

    return True, res[1], adjusted


def _eval_submodule(
    basepath: Path,
    item: GitDiffItem,
    recursion: str,
) -> GitDiffItem:
    """In-place amend GitDiffItem submodule item"""
    if recursion.endswith('-ignore-submodules'):
        return item

    item_path = basepath / item.relpath

    # this is the cheapest test for the theoretical chance that a submodule
    # is present at `item_path`. This is beneficial even when we would only
    # run a single call to `git rev-parse`
    # https://github.com/datalad/datalad-next/issues/606
    if not (item_path / '.git').exists():
        return item

    # get head commit, and whether a submodule is actually present,
    # and/or in adjusted mode
    subds_present, head_commit, adjusted = _get_submod_worktree_head(item_path)
    if not subds_present:
        return item

    modification_types = (
        _eval_submodule_adjusted(item_path, item, head_commit, recursion)
        if adjusted
        else _eval_submodule_normal(item_path, item, head_commit, recursion)
    )

    if not modification_types:
        return item

    return replace(
        item,
        status=GitDiffStatus.modification,
        modification_types=(
            *(item.modification_types or ()),
            *modification_types,
        ),
    )


def _eval_submodule_normal(
    item_path: Path,
    item: GitDiffItem,
    head_commit: str | None,
    recursion: str,
) -> list[GitContainerModificationType]:
    if (
        not recursion.endswith('-ignore-submodules-dirty')
        and item.status is None
        or (
            item.modification_types
            and GitContainerModificationType.new_commits in item.modification_types
        )
    ):
        # if new commits have been detected, the diff-implementation is
        # not able to report "modified content" at the same time, if it
        # exists. This requires a dedicated inspection, which conincidentally
        # is identical to the analysis of an adjusted mode submodule.
        return _eval_submodule_adjusted(item_path, item, head_commit, recursion)

    modification_types = []

    if item.gitsha != head_commit:
        modification_types.append(GitContainerModificationType.new_commits)

    # check for untracked content (recursively)
    if not recursion.endswith('-ignore-submodules-dirty') and _path_has_untracked(
        item_path
    ):
        modification_types.append(GitContainerModificationType.untracked_content)

    return modification_types


def _eval_submodule_adjusted(
    item_path: Path,
    item: GitDiffItem,
    head_commit: str | None,
    recursion: str,
) -> list[GitContainerModificationType]:
    # we cannot rely on the diff-report for a submodule in adjusted mode.
    # git would make the comparison to the adjusted branch HEAD alone.
    # this would almost always be invalid, because it is not meaningful to
    # track a commit in an adjusted branch (it goes away).
    #
    # instead, we need to:
    # - check for a change in the corresponding HEAD to the recorded commit
    #   in the parent repository, consider any change "new commits"
    # - check for a diff of the worktree to corresponding HEAD, consider
    #   any such diff a "modified content"
    # - and lastly check for untracked content

    # start with "no modification"
    modification_types = []

    if item.prev_gitsha != head_commit:
        modification_types.append(GitContainerModificationType.new_commits)

    if recursion.endswith('-ignore-submodules-dirty'):
        return modification_types

    if any(
        i.status is not None
        for i in iter_gitdiff(
            item_path,
            from_treeish=head_commit,
            # worktree
            to_treeish=None,
            recursion='repository-ignore-submodules-dirty',
            find_renames=None,
            find_copies=None,
        )
    ):
        modification_types.append(GitContainerModificationType.modified_content)

    # check for untracked content (recursively)
    if _path_has_untracked(item_path):
        modification_types.append(GitContainerModificationType.untracked_content)

    return modification_types


def get_worktree_head(
    path: Path,
) -> tuple[str | None, str | None]:
    """Returns the symbolic name of the worktree `HEAD` at the given path

    Returns
    -------
    tuple
      The first item is the symbolic name of the worktree `HEAD`, or `None`
      if there is no commit.
      The second item is the symbolic name of the "corresponding branch" in
      an adjusted-mode git-annex repository, or `None`.
    """
    try:
        head = call_git_lines(
            # we add the pathspec disambiguator to get cleaner error messages
            # (and we only report the first item below, to take it off again)
            ['rev-parse', '-q', '--symbolic-full-name', 'HEAD', '--'],
            cwd=path,
            # we are doing error message parsing below, fix the language
            # to avoid making it even more fragile
            force_c_locale=True,
        )[0]
    except (NotADirectoryError, FileNotFoundError) as e:
        msg = 'path not found'
        raise ValueError(msg) from e
    except CommandError as e:
        if 'fatal: not a git repository' in e.stderr:
            msg = f'no Git repository at {path!r}'
            raise ValueError(msg) from e
        if 'fatal: bad revision' in e.stderr:
            return (None, None)
        # no idea reraise
        raise  # pragma: no cover

    if head.startswith('refs/heads/adjusted/'):
        # this is a git-annex adjusted branch. do the comparison against
        # its basis. it is not meaningful to track the managed branch in
        # a superdataset
        return (
            head,
            # replace 'refs/heads' with 'refs/basis'
            f'refs/basis/{head[11:]}',
        )
    return (head, None)
