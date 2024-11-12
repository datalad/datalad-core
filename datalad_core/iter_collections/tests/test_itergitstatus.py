from itertools import chain
from pathlib import PurePosixPath

import pytest

from datalad_core.runners import (
    call_git_success,
)
from datalad_core.tests import (
    call_git_addcommit,
    create_submodule,
)

from ..gitstatus import (
    GitContainerModificationType,
    GitDiffStatus,
    _get_submod_worktree_head,
    _path_has_untracked,
    get_worktree_head,
    iter_gitstatus,
)


def test_status_homogeneity(modified_dataset):
    """Test things that should always be true, no matter the precise
    parameterization

    A main purpose of this test is also to exercise all (main) code paths.
    """
    ds = modified_dataset
    for kwargs in (
        # default
        {'path': ds},
        # same, but making the reference commit explicit
        {'path': ds, 'head': 'HEAD'},
        {'path': ds, 'recursion': 'none'},
        {'path': ds, 'recursion': 'repository'},
        {'path': ds, 'recursion': 'submodules'},
        # same as above, but with the submodules in the root
        {'path': ds / 'dir_sm', 'recursion': 'none'},
        {'path': ds / 'dir_sm', 'recursion': 'repository'},
        {'path': ds / 'dir_sm', 'recursion': 'submodules'},
        # no submodule state
        {'path': ds, 'recursion': 'none-ignore-submodules'},
        {'path': ds, 'recursion': 'repository-ignore-submodules'},
        # just the commit
        {'path': ds, 'recursion': 'none-ignore-submodules-dirty'},
        {'path': ds, 'recursion': 'repository-ignore-submodules-dirty'},
        # without untracked
        {'path': ds, 'untracked': None, 'recursion': 'none'},
        {'path': ds, 'untracked': None, 'recursion': 'repository'},
        {'path': ds, 'untracked': None, 'recursion': 'submodules'},
        # special untracked modes
        {'path': ds, 'untracked': 'whole-dir', 'recursion': 'none'},
        {'path': ds, 'untracked': 'whole-dir', 'recursion': 'repository'},
        {'path': ds, 'untracked': 'whole-dir', 'recursion': 'submodules'},
        {'path': ds, 'untracked': 'no-empty-dir', 'recursion': 'none'},
        {'path': ds, 'untracked': 'no-empty-dir', 'recursion': 'repository'},
        {'path': ds, 'untracked': 'no-empty-dir', 'recursion': 'submodules'},
        # call in the mountpoint of a dropped submodule
        {'path': ds / 'dir_sm' / 'droppedsm_c'},
    ):
        st = {item.relpath: item for item in iter_gitstatus(**kwargs)}
        # we get no report on anything clean (implicitly also tests
        assert all(not i.relpath.name.endswith('_c') for i in st.values())

        # anything untracked is labeled as such
        assert all(
            i.status == GitDiffStatus.other
            # we would not see a submodule modification qualifier when instructed
            # not to evaluate a submodule
            or 'ignore-submodules' in kwargs.get('recursion', '')
            or GitContainerModificationType.untracked_content in i.modification_types
            for i in st.values()
            if 'u' in i.relpath.name.split('_')[1]
        )

        # anything modified is labeled as such
        assert all(
            # either directly
            i.status == GitDiffStatus.modification
            # or as an addition with a modification on top
            or (
                i.status == GitDiffStatus.addition
                and GitContainerModificationType.modified_content
                in i.modification_types
            )
            for i in st.values()
            if 'm' in i.relpath.name.split('_')[1]
        )

        # anything deleted is labeled as such
        assert all(
            i.status == GitDiffStatus.deletion
            for i in st.values()
            if 'd' in i.relpath.name.split('_')[1]
        )


def test_status_invalid_params(gitrepo):
    with pytest.raises(ValueError, match='unknown recursion type'):
        list(iter_gitstatus(gitrepo, recursion='fromspace'))


test_cases_repository_recursion = [
    {'name': 'file_a', 'status': GitDiffStatus.addition},
    {'name': 'dir_m/file_a', 'status': GitDiffStatus.addition},
    {'name': 'file_u', 'status': GitDiffStatus.other},
    {'name': 'dir_u/file_u', 'status': GitDiffStatus.other},
    {'name': 'dir_m/file_u', 'status': GitDiffStatus.other},
    {'name': 'dir_m/dir_u/file_u', 'status': GitDiffStatus.other},
    {'name': 'file_d', 'status': GitDiffStatus.deletion},
    {'name': 'dir_d/file_d', 'status': GitDiffStatus.deletion},
    {'name': 'dir_m/file_d', 'status': GitDiffStatus.deletion},
    {'name': 'file_m', 'status': GitDiffStatus.modification},
    {'name': 'dir_m/file_m', 'status': GitDiffStatus.modification},
    {'name': 'dir_sm/sm_d', 'status': GitDiffStatus.deletion},
    {
        'name': 'dir_sm/sm_n',
        'status': GitDiffStatus.modification,
        'qual': (GitContainerModificationType.new_commits,),
    },
    {
        'name': 'dir_sm/sm_m',
        'status': GitDiffStatus.modification,
        'qual': (GitContainerModificationType.modified_content,),
    },
    {
        'name': 'dir_sm/sm_nm',
        'status': GitDiffStatus.modification,
        'qual': (
            GitContainerModificationType.modified_content,
            GitContainerModificationType.new_commits,
        ),
    },
    {
        'name': 'dir_sm/sm_nmu',
        'status': GitDiffStatus.modification,
        'qual': (
            GitContainerModificationType.modified_content,
            GitContainerModificationType.untracked_content,
            GitContainerModificationType.new_commits,
        ),
    },
    {
        'name': 'dir_sm/sm_u',
        'status': GitDiffStatus.modification,
        'qual': (GitContainerModificationType.untracked_content,),
    },
    {
        'name': 'dir_sm/sm_mu',
        'status': GitDiffStatus.modification,
        'qual': (
            GitContainerModificationType.modified_content,
            GitContainerModificationType.untracked_content,
        ),
    },
]

test_cases_submodule_recursion = [
    {'name': 'dir_sm/sm_m/file_a', 'status': GitDiffStatus.addition},
    {'name': 'dir_sm/sm_nm/file_a', 'status': GitDiffStatus.addition},
    {'name': 'dir_sm/sm_mu/file_a', 'status': GitDiffStatus.addition},
    {'name': 'dir_sm/sm_nmu/file_a', 'status': GitDiffStatus.addition},
    {'name': 'dir_sm/sm_m/file_m', 'status': GitDiffStatus.modification},
    {'name': 'dir_sm/sm_mu/file_m', 'status': GitDiffStatus.modification},
    {'name': 'dir_sm/sm_nmu/file_m', 'status': GitDiffStatus.modification},
    {'name': 'dir_sm/sm_u/file_u', 'status': GitDiffStatus.other},
    {'name': 'dir_sm/sm_mu/file_u', 'status': GitDiffStatus.other},
    {'name': 'dir_sm/sm_nmu/file_u', 'status': GitDiffStatus.other},
    {'name': 'dir_sm/sm_u/dir_u/file_u', 'status': GitDiffStatus.other},
    {'name': 'dir_sm/sm_mu/dir_u/file_u', 'status': GitDiffStatus.other},
    {'name': 'dir_sm/sm_nmu/dir_u/file_u', 'status': GitDiffStatus.other},
]


def _assert_testcases(st, tc):
    for c in tc:
        assert st[c['name']].status == c['status']
        mod_types = st[c['name']].modification_types
        if 'qual' in c:
            assert set(mod_types) == set(c['qual']), f'Mismatch for {c=!r}'
        else:
            assert mod_types is None


def test_status_vs_git(modified_dataset):
    """Implements a comparison against how git-status behaved when
    the test was written  (see fixture docstring)
    """
    st = {
        str(item.relpath): item
        for item in iter_gitstatus(
            path=modified_dataset,
            recursion='repository',
            untracked='all',
        )
    }
    _assert_testcases(st, test_cases_repository_recursion)


def test_status_norec(modified_dataset):
    st = {
        str(item.relpath): item
        for item in iter_gitstatus(
            path=modified_dataset,
            recursion='none',
            untracked='all',
        )
    }
    test_cases = [
        {'name': 'file_a', 'status': GitDiffStatus.addition},
        {'name': 'dir_d', 'status': GitDiffStatus.deletion},
        {
            'name': 'dir_m',
            'status': GitDiffStatus.modification,
            'qual': (
                GitContainerModificationType.modified_content,
                GitContainerModificationType.untracked_content,
            ),
        },
        {
            'name': 'dir_sm',
            'status': GitDiffStatus.modification,
            'qual': (
                GitContainerModificationType.modified_content,
                GitContainerModificationType.untracked_content,
            ),
        },
        {'name': 'file_d', 'status': GitDiffStatus.deletion},
        {'name': 'file_m', 'status': GitDiffStatus.modification},
        {'name': 'dir_u', 'status': GitDiffStatus.other},
        {'name': 'file_u', 'status': GitDiffStatus.other},
    ]
    _assert_testcases(st, test_cases)


def test_status_smrec(modified_dataset):
    st = {
        str(item.relpath): item
        for item in iter_gitstatus(
            path=modified_dataset,
            recursion='submodules',
            untracked='all',
        )
    }
    # in this mode we expect ALL results of a 'repository' mode recursion,
    # including the submodule-type items, plus additional ones from within
    # the submodules
    _assert_testcases(
        st, chain(test_cases_repository_recursion, test_cases_submodule_recursion)
    )


def test_status_monorec(modified_dataset):
    st = {
        str(item.relpath): item
        for item in iter_gitstatus(
            path=modified_dataset,
            recursion='monolithic',
            untracked='all',
        )
    }
    # in this mode we expect ALL results of a 'repository' mode recursion,
    # including the submodule-type items, plus additional ones from within
    # the submodules
    _assert_testcases(
        st,
        # repository and recursion test cases
        [
            c
            for c in chain(
                test_cases_repository_recursion, test_cases_submodule_recursion
            )
            # minus any submodule that have no new commits
            # (this only thing that is not attributable to individual
            # content changes)
            if c['name'].split('/')[-1]
            not in (
                'sm_m',
                'sm_mu',
                'sm_u',
            )
        ],
    )


def test_status_gitinit(tmp_path):
    # initialize a fresh git repo, but make no commits
    assert call_git_success(['init'], cwd=tmp_path)
    for recmode in ('none', 'repository', 'submodules'):
        assert [] == list(iter_gitstatus(tmp_path, recursion=recmode))
    # untracked reporting must be working normal
    (tmp_path / 'untracked').touch()
    for recmode in ('none', 'repository', 'submodules'):
        res = list(iter_gitstatus(tmp_path, recursion=recmode))
        assert len(res) == 1
        assert res[0].relpath.name == 'untracked'
        assert res[0].status == GitDiffStatus.other


def test_status_nohead_staged(tmp_path):
    # initialize a fresh git repo, but make no commits
    assert call_git_success(['init'], cwd=tmp_path)
    # stage a file
    (tmp_path / 'probe').write_text('tostage')
    assert call_git_success(['add', 'probe'], cwd=tmp_path)
    _assert_testcases(
        {str(i.relpath): i for i in iter_gitstatus(tmp_path)},
        [{'name': 'probe', 'status': GitDiffStatus.addition}],
    )


def test_status_submodule_added(gitrepo):
    subm_relpath = PurePosixPath('sub')
    create_submodule(gitrepo, subm_relpath)
    # check that we get the status on a submodule that was just added with
    # no additional changes
    res = list(iter_gitstatus(gitrepo, recursion='monolithic'))
    assert any(
        i.relpath == subm_relpath and i.gitsha and i.prev_gitsha is None for i in res
    )


def test_path_has_untracked(gitrepo):
    assert _path_has_untracked(gitrepo / 'nothere') is False
    assert _path_has_untracked(gitrepo) is False
    (gitrepo / 'untracked_file').touch()
    assert _path_has_untracked(gitrepo) is True


def test_get_submod_worktree_head(gitrepo):
    with pytest.raises(
        RuntimeError,
        match='must not be used on a non-submodule',
    ):
        _get_submod_worktree_head(gitrepo)

    subm_relpath = PurePosixPath('subm')
    subm_path = gitrepo / subm_relpath
    # does not exist yet
    assert _get_submod_worktree_head(subm_path) == (False, None, False)

    create_submodule(gitrepo, subm_relpath)
    call_git_addcommit(gitrepo)

    non_subm_path = gitrepo / 'dir'
    non_subm_path.mkdir()
    # TODO: will return actual adjusted prop of parent
    # I think this should runtime error
    assert _get_submod_worktree_head(non_subm_path) == (False, None, False)


def test_get_worktree_head(tmp_path):
    with pytest.raises(ValueError, match='no Git repo'):
        get_worktree_head(tmp_path)
