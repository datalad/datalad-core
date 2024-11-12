import shutil
from pathlib import PurePosixPath

import pytest

from datalad_core.consts import PRE_INIT_COMMIT_SHA
from datalad_core.repo import Worktree
from datalad_core.runners import call_git
from datalad_core.tests import (
    call_git_addcommit,
    create_submodule,
    rmtree,
)

from ..gitdiff import (
    GitDiffStatus,
    GitTreeItemType,
    iter_gitdiff,
)


def test_iter_gitdiff_invalid():
    with pytest.raises(ValueError, match='either.*or.*must not be None'):
        # no meaningful comparison
        list(iter_gitdiff('.', None, None))
    with pytest.raises(ValueError, match='unknown'):
        # unsupported recursion mode
        list(iter_gitdiff('.', None, None, recursion='all'))


def test_iter_gitdiff_basic(gitrepo):
    # we use two distinct content blobs below, hardcode sha here
    # for readability
    empty_sha = 'e69de29bb2d1d6434b8b29ae775ad8c2e48c5391'
    content = '123'
    content_sha = 'd800886d9c86731ae5c4a62b0b77c437015e00d2'
    # clean dataset, no items
    assert list(iter_gitdiff(gitrepo, PRE_INIT_COMMIT_SHA, None)) == []
    testpath = gitrepo / 'sub' / 'test'
    testpath.parent.mkdir()
    testpath.touch()
    # dataset with untracked file, no items
    assert list(iter_gitdiff(gitrepo, PRE_INIT_COMMIT_SHA, None)) == []
    call_git_addcommit(gitrepo)
    # clean dataset again, no items, compared to HEAD
    assert list(iter_gitdiff(gitrepo, 'HEAD', None)) == []
    # added file
    diff = list(iter_gitdiff(gitrepo, PRE_INIT_COMMIT_SHA, 'HEAD'))
    assert len(diff) == 1
    di = diff[0]
    assert di.status == GitDiffStatus.addition
    assert di.relpath == PurePosixPath('sub/test')
    assert di.prev_relpath is di.prev_gitsha is di.prev_gittype is None
    assert di.gitsha == empty_sha
    assert di.gittype == GitTreeItemType.file
    # modified file
    testpath.write_text(content)
    diff = list(iter_gitdiff(gitrepo, 'HEAD', None))
    assert len(diff) == 1
    di = diff[0]
    # labeled as modified
    assert di.status == GitDiffStatus.modification
    # the name is POSIX
    assert di.relpath == di.prev_relpath == PurePosixPath('sub/test')
    # unstaged modification reports no shasum
    assert di.gitsha is None
    assert di.prev_gitsha == empty_sha
    assert di.gittype == di.prev_gittype == GitTreeItemType.file
    # make clean
    call_git_addcommit(gitrepo)
    moved_testpath = testpath.parent / 'moved_test'
    testpath.rename(moved_testpath)
    # renamed file, unstaged, reported as deletion, we do not see the addition
    # yet (untracked)
    diff = list(iter_gitdiff(gitrepo, 'HEAD', None))
    assert len(diff) == 1
    di = diff[0]
    assert di.status == GitDiffStatus.deletion
    assert di.relpath == di.prev_relpath == PurePosixPath('sub/test')
    assert di.prev_gitsha == content_sha
    assert di.prev_gittype == GitTreeItemType.file
    assert di.gitsha is di.gittype is None
    # make clean
    call_git_addcommit(gitrepo)
    # now we can look at the rename
    complete_percentage = 100
    diff = list(iter_gitdiff(gitrepo, 'HEAD~1', 'HEAD', find_renames=100))
    assert len(diff) == 1
    di = diff[0]
    assert di.status == GitDiffStatus.rename
    assert di.relpath == PurePosixPath('sub/moved_test')
    assert di.prev_relpath == PurePosixPath('sub/test')
    assert di.gitsha == di.prev_gitsha == content_sha
    assert di.prev_gittype is di.gittype is GitTreeItemType.file
    assert di.percentage == complete_percentage
    # now a copy
    shutil.copyfile(moved_testpath, testpath)
    call_git_addcommit(gitrepo)
    diff = list(iter_gitdiff(gitrepo, 'HEAD~1', 'HEAD', find_copies=100))
    assert len(diff) == 1
    di = diff[0]
    assert di.status == GitDiffStatus.copy
    assert di.relpath == PurePosixPath('sub/test')
    assert di.prev_relpath == PurePosixPath('sub/moved_test')
    assert di.gitsha == di.prev_gitsha == content_sha
    assert di.percentage == complete_percentage
    # now replace file with submodule
    testpath.unlink()
    # we must safe to appease datalad's content collision detection
    call_git_addcommit(gitrepo)
    # intermediate smoke test for describing a single tree (diff from parents)
    diff = list(iter_gitdiff(gitrepo, None, 'HEAD'))
    assert len(diff) == 1
    assert diff[0].status == GitDiffStatus.deletion
    # now cause typechange
    testpath.mkdir()
    Worktree.init_at(testpath)
    (testpath / '.gitkeep').touch()
    call_git_addcommit(testpath)
    call_git(
        ['submodule', 'add', f'./{testpath}', f'{testpath.relative_to(gitrepo)}'],
        cwd=gitrepo,
        capture_output=True,
    )
    call_git_addcommit(gitrepo)
    diff = list(
        iter_gitdiff(
            gitrepo,
            # because we have an intermediate safe, compare to two states
            # back
            'HEAD~2',
            'HEAD',
        )
    )
    assert len(diff) == len(['.gitmodules', 'sub/test'])
    # let's ignore the uninteresting .gitmodules addition for further tests
    di = next(i for i in diff if i.relpath != PurePosixPath('.gitmodules'))
    assert di.status == GitDiffStatus.typechange
    assert di.relpath == di.prev_relpath == PurePosixPath('sub/test')
    assert di.gitsha != di.prev_gitsha
    assert di.prev_gitsha == content_sha
    assert di.prev_gittype == GitTreeItemType.file
    assert di.gittype == GitTreeItemType.submodule


def test_iter_gitdiff_nonroot(gitrepo):
    # all tests are concerned with running not in the dataset root
    root = gitrepo
    nonroot = root / 'sub'
    nonroot.mkdir()

    # nothing to report, no problem
    assert list(iter_gitdiff(nonroot, PRE_INIT_COMMIT_SHA, None)) == []
    # change above CWD is not reported
    (root / 'rootfile').touch()
    call_git_addcommit(gitrepo)
    assert list(iter_gitdiff(nonroot, PRE_INIT_COMMIT_SHA, 'HEAD')) == []
    # check worktree modification detection too
    (root / 'rootfile').write_text('some')
    assert list(iter_gitdiff(nonroot, 'HEAD', None)) == []
    # and now test that reporting is relative to
    # CWD
    (nonroot / 'nonrootfile').touch()
    call_git_addcommit(gitrepo)
    assert next(iter_gitdiff(nonroot, 'HEAD~1', 'HEAD')).relpath == PurePosixPath(
        'nonrootfile'
    )
    (nonroot / 'nonrootfile').write_text('other')
    assert next(iter_gitdiff(nonroot, 'HEAD~1', 'HEAD')).relpath == PurePosixPath(
        'nonrootfile'
    )


def test_iter_gitdiff_nonrec(gitrepo):
    subdir = gitrepo / 'sub'
    subdir.mkdir()
    for fn in ('f1.txt', 'f2.txt'):
        (subdir / fn).touch()
    call_git_addcommit(gitrepo)
    diff = list(iter_gitdiff(gitrepo, PRE_INIT_COMMIT_SHA, 'HEAD', recursion='none'))
    assert len(diff) == 1
    di = diff[0]
    assert di.relpath == PurePosixPath('sub')
    assert di.gittype == GitTreeItemType.directory
    assert di.status == GitDiffStatus.addition
    di_tree = di
    # same behavior for a worktree modification
    for fn in ('f1.txt', 'f2.txt'):
        (subdir / fn).write_text('modified')
    diff = list(iter_gitdiff(gitrepo, PRE_INIT_COMMIT_SHA, None, recursion='none'))
    assert len(diff) == 1
    di = diff[0]
    # these are identical to the diff-tree based report
    for p in ('relpath', 'gittype', 'prev_gitsha', 'prev_gittype'):
        assert getattr(di, p) == getattr(di_tree, p)
    # and there are different
    # not staged, no gitsha
    assert di.gitsha is None
    # it does no type inference for the previous state (expensive)
    assert di.prev_gittype is None

    # when the directory existed in the from-state it becomes a
    # modification
    diff = list(iter_gitdiff(gitrepo, 'HEAD', None, recursion='none'))
    assert len(diff) == 1
    assert diff[0].status == GitDiffStatus.modification

    # now remove the subdir
    rmtree(subdir)
    diff = list(iter_gitdiff(gitrepo, 'HEAD', None, recursion='none'))
    assert len(diff) == 1
    # it still reports a modification, even though the directory is empty/gone.
    # it would require a filesystem STAT to detect a deletion, and a further
    # type investigation in `from_treeish` to detect a type change.
    # This is not done until there is evidence for a real use case
    assert diff[0].status == GitDiffStatus.modification


def test_iter_gitdiff_typechange_issue6791(gitrepo):
    # verify that we can handle to problem described in
    # https://github.com/datalad/datalad/issues/6791
    #
    # a subdataset is wiped out (uncommitted) and replaced by a file
    test_relpath = PurePosixPath('test')
    test_path = gitrepo / test_relpath
    create_submodule(gitrepo, test_relpath)
    # commit the submodule addition
    call_git_addcommit(gitrepo)
    rmtree(test_path)
    test_path.touch()
    diff = list(iter_gitdiff(gitrepo, 'HEAD', None))
    assert len(diff) == 1
    di = diff[0]
    assert di.status == GitDiffStatus.typechange
    assert di.relpath == di.prev_relpath == test_relpath
    # unstaged change
    assert di.gitsha is None
    assert di.prev_gittype == GitTreeItemType.submodule
    assert di.gittype == GitTreeItemType.file


def test_iter_gitdiff_rec(gitrepo):
    subm_relpath = PurePosixPath('subds')
    subm_wt = create_submodule(gitrepo, subm_relpath)
    call_git_addcommit(gitrepo)

    diff = list(
        iter_gitdiff(gitrepo, PRE_INIT_COMMIT_SHA, 'HEAD', recursion='submodules')
    )
    # we get .gitmodules and a submodule record
    assert len(diff) == len(['.gitmodules', 'subds'])
    # the entire submodule is new and the first one, so everything
    # is an addition
    assert all(i.status == GitDiffStatus.addition for i in diff)
    # only files, no submodule record, by default
    assert all(i.gittype == GitTreeItemType.file for i in diff)

    # when we ask for it, we get the submodule item too
    diff_w_sm = list(
        iter_gitdiff(
            gitrepo,
            PRE_INIT_COMMIT_SHA,
            'HEAD',
            recursion='submodules-and-yield',
        )
    )
    assert len(diff) + 1 == len(diff_w_sm)
    assert any(
        i.relpath == subm_relpath and i.gittype == GitTreeItemType.submodule
        for i in diff_w_sm
    )

    # smoke test for an all-clean diff against the worktrees
    assert list(iter_gitdiff(gitrepo, 'HEAD', None, recursion='submodules')) == []

    # make subdataset record modified
    subm_test_relpath = subm_relpath / 'file'
    subm_test_path = gitrepo / subm_test_relpath
    subm_test_path.touch()
    call_git_addcommit(subm_wt.path)
    diff = list(iter_gitdiff(gitrepo, 'HEAD', None, recursion='submodules'))
    assert len(diff) == 1
    di = diff[0]
    assert di.relpath == subm_test_relpath
    assert di.status == GitDiffStatus.addition
    # now with submodule item
    diff_w_sm = list(
        iter_gitdiff(gitrepo, 'HEAD', None, recursion='submodules-and-yield')
    )
    assert len(diff_w_sm) == len(diff) + 1
    di = diff_w_sm[0]
    # the submodule item is always first
    assert di.relpath == subm_relpath
    assert di.gittype == GitTreeItemType.submodule
    assert di.status == GitDiffStatus.modification
    assert diff_w_sm[1] == diff[0]

    # safe the whole hierarchy
    call_git_addcommit(gitrepo)
    # we get the exact same change report via the diff to HEAD~1:HEAD
    assert diff == list(iter_gitdiff(gitrepo, 'HEAD~1', 'HEAD', recursion='submodules'))

    # modify a tracked file in the subdataset
    subm_test_path.write_text('123')
    diff_w_sm = list(
        iter_gitdiff(gitrepo, 'HEAD', None, recursion='submodules-and-yield')
    )
    # same report for the submodule (and it is first again)
    assert diff_w_sm[0].relpath == subm_relpath
    assert diff_w_sm[0].gittype == GitTreeItemType.submodule
    assert diff_w_sm[0].status == GitDiffStatus.modification
    # but this time the file is not an addition but a modification
    assert diff_w_sm[1].relpath == subm_test_relpath
    assert diff_w_sm[1].status == GitDiffStatus.modification

    # force-wipe the subdataset, and create a condition where the subdatasets
    # is expected but missing
    rmtree(subm_wt.path)
    diff = list(iter_gitdiff(gitrepo, 'HEAD', None))
    assert len(diff) == 1
    di = diff[0]
    assert di.relpath == subm_relpath
    assert di.status == GitDiffStatus.deletion
    # if we now run with recursion, we get the exact same result, the absent
    # submodule is a subtree that we do not recurse into, hence the report
    # is only on the tree itself
    assert diff == list(iter_gitdiff(gitrepo, 'HEAD', None, recursion='submodules'))


def test_iter_gitdiff_multilvl_rec(gitrepo):
    # for uniformity with the coming submodules
    (gitrepo / '.gitkeep').touch()
    s1_relpath = PurePosixPath('sublvl1')
    s1_wt = create_submodule(gitrepo, s1_relpath)
    s2_relpath = PurePosixPath('sublvl2')
    create_submodule(s1_wt.path, s2_relpath)
    call_git_addcommit(s1_wt.path)
    call_git_addcommit(gitrepo)

    diff = list(
        iter_gitdiff(
            gitrepo,
            PRE_INIT_COMMIT_SHA,
            'HEAD',
            # check that we get full repo content from all submodules
            recursion='submodules-and-yield',
        )
    )
    for relpath in (s1_relpath, s1_relpath / s2_relpath):
        assert any(
            d.relpath == relpath and d.gittype == GitTreeItemType.submodule
            for d in diff
        )
    for base in (
        PurePosixPath('.'),
        s1_relpath,
        s1_relpath / s2_relpath,
    ):
        assert any(
            d.relpath == base / '.gitkeep' and d.gittype == GitTreeItemType.file
            for d in diff
        )

    # try with very simple pathspec constraint, where the pathspec
    # itself does not match the submodules that contain the
    # matches
    diff = list(
        iter_gitdiff(
            gitrepo,
            PRE_INIT_COMMIT_SHA,
            'HEAD',
            pathspecs=[':(glob)**/.gitkeep'],
            recursion='submodules',
        )
    )
    n_repos = 3
    assert len(diff) == n_repos
    assert all(
        d.relpath.name == '.gitkeep' and d.gittype == GitTreeItemType.file for d in diff
    )


def test_iter_gitdiff_recmodes(modified_dataset):
    # running in a dir with only submodules, non-recursion, gives
    # nothing
    sm_args = (modified_dataset / 'dir_sm', 'HEAD', None)
    for recmode in ('none-ignore-submodules', 'repository-ignore-submodules'):
        diff = list(iter_gitdiff(*sm_args, recursion=recmode))
        assert not len(diff)
    # when only ignoring dirty-states, we get anything with new commits,
    # or deletions
    for recmode in (
        'none-ignore-submodules-dirty',
        'repository-ignore-submodules-dirty',
    ):
        diff = list(iter_gitdiff(*sm_args, recursion=recmode))
        assert all(i.relpath.name.startswith(('sm_n', 'sm_d')) for i in diff)
    diff = list(iter_gitdiff(*sm_args, recursion='none'))
    assert all(i.relpath.name.startswith('sm_') for i in diff)
