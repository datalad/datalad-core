from pathlib import (
    PurePosixPath,
)

import pytest

from datalad_core.iter_collections.gitworktree import (
    _lsfiles_line2item,
    iter_gitworktree,
    iter_submodules,
)
from datalad_core.repo import (
    GitTreeItemType,
    WorktreeDirectory,
    WorktreeItem,
)
from datalad_core.tests import call_git_addcommit


def test_iter_gitworktree(gitrepo):
    (gitrepo / 'emptydir').mkdir()
    tracked_file_relpath = PurePosixPath('subdir_tracked') / 'tracked'
    untracked_file_relpath = PurePosixPath('subdir_untracked') / 'untracked'
    for p in (tracked_file_relpath, untracked_file_relpath):
        p_abs = gitrepo / p
        p_abs.parent.mkdir()
        p_abs.write_text(p.name)
    call_git_addcommit(gitrepo, [str(tracked_file_relpath)])

    tracked_items = list(iter_gitworktree(gitrepo, untracked=None))
    # without untracked's and no link resolution this is plain and fast
    assert all(
        isinstance(i, WorktreeItem) and i.gitsha and i.gittype for i in tracked_items
    )

    all_items = list(iter_gitworktree(gitrepo, untracked='all'))
    # empty-dir is not reported, only untracked files
    assert len(all_items) == len(tracked_items) + 1
    assert any(
        i.relpath == untracked_file_relpath and i.gitsha is None and i.gittype is None
        for i in all_items
    )
    # same again, but with a different untracked reporting
    all_items = list(iter_gitworktree(gitrepo, untracked='whole-dir'))
    # emptydir is reported too
    assert len(all_items) == len(tracked_items) + 2
    assert any(
        i.relpath == untracked_file_relpath.parent
        and i.gitsha is None
        and i.gittype is None
        for i in all_items
    )
    # and again for the last variant
    all_items = list(iter_gitworktree(gitrepo, untracked='no-empty-dir'))
    # and again no emptydir
    assert len(all_items) == len(tracked_items) + 1
    assert any(
        i.relpath == untracked_file_relpath.parent
        and i.gitsha is None
        and i.gittype is None
        for i in all_items
    )


def test_name_starting_with_tab(gitrepo):
    tabbed_file_name = '\ttab.txt'
    tabbed_file = gitrepo / tabbed_file_name
    try:
        tabbed_file.write_text('name of this file starts with a tab')
    except OSError:
        pytest.skip('not applicable on crippled filesystems')

    call_git_addcommit(gitrepo, [tabbed_file])

    iter_paths = [item.path for item in iter_gitworktree(gitrepo)]
    assert tabbed_file in iter_paths


def test_iter_gitworktree_recursive(gitrepo):
    # actually, this tests non-recursive, because within-repo
    # recursion is the default.
    # later, we might also test subdataset recursion here
    # some tracked content
    tracked1 = gitrepo / 'tracked1'
    tracked2 = gitrepo / 'subdir' / 'tracked2'
    tracked3 = gitrepo / 'subdir' / 'tracked3'
    for p in (tracked1, tracked2, tracked3):
        p.parent.mkdir(exist_ok=True)
        p.write_text(p.name)
    call_git_addcommit(gitrepo)

    # an "invisible" directory (no content)
    (gitrepo / 'emptydir').mkdir()
    # untracked file in subdir
    untracked = gitrepo / 'subdir_u' / 'untracked'
    untracked.parent.mkdir()
    untracked.write_text('untracked')

    # matches git report with untracked=all
    all_content = {
        PurePosixPath('subdir'),
        PurePosixPath('subdir_u'),
        PurePosixPath('tracked1'),
    }
    # without any recursion, we see all top-level content, except for
    # the empty directory with no content
    all_items = list(iter_gitworktree(gitrepo, recursion='none'))
    assert {i.relpath for i in all_items} == all_content

    # no we test a query that gooey would want to make,
    # give me all content in a single directory, and also include any
    # untracked files and even untracked/empty directories
    all_items = list(iter_gitworktree(gitrepo, recursion='none', untracked='whole-dir'))
    assert {i.relpath for i in all_items} == all_content.union(
        (PurePosixPath('emptydir'),)
    )


def test_iter_gitworktree_empty(gitrepo):
    all_items = list(iter_gitworktree(gitrepo))
    assert len(all_items) == 0


@pytest.mark.usefixtures('skip_when_symlinks_not_supported')
def test_iter_gitworktree_deadsymlinks(gitrepo):
    dpath = gitrepo / 'subdir'
    dpath.mkdir()
    fpath = dpath / 'file1'
    fpath.symlink_to(gitrepo / 'not_present')
    call_git_addcommit(gitrepo)
    try:
        # we cannot read the file
        fpath.read_text()
        pytest.fail(
            'we must not get here, ' 'an exception must be raised before'
        )  # pragma: no cover
    except FileNotFoundError:
        # with dead symlinks, we end up here and that is normal
        pass
    # next one must not crash
    all_items = list(iter_gitworktree(dpath))
    # we get our "dead symlink" -- but depending on the p[latform
    # it may take a different form, hence not checking for type
    assert len(all_items) == 1
    assert all_items[0].relpath == PurePosixPath('file1')


def test_iter_gitworktree_untracked_only(modified_dataset):
    p = modified_dataset
    # only untracked files
    repo_items = list(iter_gitworktree(p, untracked='only'))
    assert all(f.path.name == 'file_u' for f in repo_items)

    # same report, but compressed to immediate directory children
    dir_items = list(iter_gitworktree(p, untracked='only', recursion='none'))
    assert {f.relpath.parts[0] for f in repo_items} == {
        f.relpath.name for f in dir_items
    }
    # no wholly untracked directories in standard report
    assert not any(
        f.path.name == 'dir_u' for f in iter_gitworktree(p, untracked='only')
    )
    # but this can be requested
    wholedir_items = list(iter_gitworktree(p, untracked='only-whole-dir'))
    assert any(f.path.name == 'dir_u' for f in wholedir_items)
    # smoke test remaining mode, test case doesn't cause difference
    assert any(f.path.name == 'dirempty_u' for f in wholedir_items)
    assert not any(
        f.path.name == 'dirempty_u'
        for f in iter_gitworktree(p, untracked='only-no-empty-dir')
    )


def test_iter_gitworktree_pathspec(modified_dataset):
    p = modified_dataset
    # TODO: bring this back -- for now, this test is running on a plain git repo
    # with no such files
    # # query for any files that are set to go straight to Git. these are just
    # # dotfiles in the default config
    # items = list(iter_gitworktree(
    #     p,
    #     pathspecs=[':(attr:annex.largefiles=nothing)']))
    # assert items
    # assert all(str(i.name).startswith('.') for i in items)
    # glob-styles
    n_added_toplevel = 1
    n_added = 2
    # first some that only give a top-level match
    assert len(list(iter_gitworktree(p, pathspecs=['file_a']))) == n_added_toplevel
    assert (
        len(list(iter_gitworktree(p, pathspecs=[':(glob)*file_a']))) == n_added_toplevel
    )
    # now some that match at any depth
    assert len(list(iter_gitworktree(p, pathspecs=['*file_a']))) == n_added
    assert len(list(iter_gitworktree(p, pathspecs=[':(glob)**/file_a']))) == n_added

    # some that do not match
    assert not list(iter_gitworktree(p, pathspecs=['*NOOO']))
    assert not list(iter_gitworktree(p, pathspecs=[':(glob)**/NOOO']))

    # some that do not match after translation to a submodule
    assert not list(
        iter_gitworktree(p, recursion='submodules', pathspecs=['dir_sm/sm_nmu/NOOO/*'])
    )


def test_iter_submodules(modified_dataset):
    p = modified_dataset
    all_sm = list(iter_submodules(p))
    assert all_sm
    assert all(sm.gittype == GitTreeItemType.submodule for sm in all_sm)
    assert all(str(sm.relpath.parent) == 'dir_sm' for sm in all_sm)
    assert sorted([str(sm.path.name) for sm in all_sm]) == [
        'droppedsm_c',
        'sm_c',
        'sm_d',
        'sm_m',
        'sm_mu',
        'sm_n',
        'sm_nm',
        'sm_nmu',
        'sm_u',
    ]
    # constrain by pathspec
    res = list(iter_submodules(p, pathspecs=['*/sm_c']))
    assert len(res) == 1
    assert res[0].relpath == PurePosixPath('dir_sm', 'sm_c')
    # test negative condition
    res = list(iter_submodules(p, pathspecs=[':(exclude)*/sm_c']))
    assert len(res) == len(all_sm) - 1
    assert not any(r.relpath == PurePosixPath('dir_sm', 'sm_c') for r in res)

    # test pathspecs matching inside submodules
    # baseline, pointing inside a submodule gives no matching results
    assert not list(iter_submodules(p, pathspecs=['dir_sm/sm_c/.datalad']))
    # we can discover the submodule that could have content that matches
    # the pathspec
    res = list(
        iter_submodules(p, pathspecs=['dir_sm/sm_c/.datalad'], match_containing=True)
    )
    assert len(res) == 1
    assert res[0].relpath == PurePosixPath('dir_sm', 'sm_c')
    # if we use a wildcard that matches any submodule, we also get all of them
    # and this includes the dropped submodule, because iter_submodules()
    # make no assumptions on what this information will be used for
    res = list(iter_submodules(p, pathspecs=['*/.datalad'], match_containing=True))
    assert len(res) == len(all_sm)


def test_iter_gitworktree_subm_recursion(modified_dataset):
    p = modified_dataset
    wd = WorktreeDirectory.from_path(p)
    nmu_items = list(iter_gitworktree(p / 'dir_sm' / 'sm_nmu', recursion='repository'))
    # doesn't matter how many exactly, but we expect multiple.
    # needed for the logic below
    assert len(nmu_items) > 1
    # and now from the top with recursion

    items = list(iter_gitworktree(p, recursion='submodules'))
    # homogeneous basedir report
    assert all(i.basedir == wd for i in items)
    # we see all the submodule content
    assert all(
        any(i.relpath == PurePosixPath('dir_sm', 'sm_nmu') / nmu.relpath for i in items)
        for nmu in nmu_items
    )
    # now we try listing only the 'nmu' submodule with a bunch of
    # equivalent pathspecs
    for ps in (
        # matches submodule directly
        ['dir_sm/sm_nmu'],
        # matches only inside the submodule
        # (test discovery of the submodule itself)
        ['dir_sm/sm_nmu/*'],
        [':(glob)dir_sm/sm_nmu/**'],
        [':(glob)dir_s?/*_nmu'],
    ):
        ps_items = [
            i.relpath for i in iter_gitworktree(p, recursion='submodules', pathspecs=ps)
        ]
        # we see the submodule items, all of them, and only those
        assert ps_items == [
            PurePosixPath('dir_sm', 'sm_nmu') / i.relpath for i in nmu_items
        ], f'Mismatch for pathspec {ps!r}'


def test_lsfiles_line2item(gitrepo):
    # untracked
    basedir = WorktreeDirectory.from_path(gitrepo)
    assert _lsfiles_line2item(basedir, 'some/file.txt') == WorktreeItem(
        basedir=basedir, relpath=PurePosixPath('some', 'file.txt')
    )
    # tracked
    mode = '100644'
    sha = '973b097e6cb3b2eb498dec32a021137cec842de8'
    stage = '0'
    fname = 'docs/Makefile'
    assert _lsfiles_line2item(
        basedir,
        f'{mode} {sha} {stage}\t{fname}',
    ) == WorktreeItem(
        basedir=basedir,
        relpath=PurePosixPath(fname),
        gitsha=sha,
        gittype=GitTreeItemType.file,
    )
    # anything else
    assert _lsfiles_line2item(
        basedir,
        'BURP\tsome/file.txt',
    ) == WorktreeItem(
        basedir=basedir,
        relpath=PurePosixPath('some', 'file.txt'),
    )
