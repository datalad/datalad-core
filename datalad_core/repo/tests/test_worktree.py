import pytest

from datalad_core.config import ConfigItem
from datalad_core.runners import (
    call_annex_json_lines,
    call_git,
)

from ..worktree import Worktree


def test_worktree(gitrepo):
    wt = Worktree(gitrepo)
    assert str(wt) == f'Worktree({gitrepo})'
    assert repr(wt) == f'Worktree({gitrepo!r})'
    assert str(gitrepo / '.git' / 'config') in str(wt.config)
    assert str(gitrepo / '.git' / 'config') in repr(wt.config)
    # sources without content are not reported
    assert 'DataladBranchConfig' not in str(wt.config)
    # only in repr()
    assert 'DataladBranchConfig' in repr(wt.config)

    # main worktree does not shares config manager with repo
    # (at least the datalad branch config sources is pointing
    # to the worktree, not the repo directly)
    assert wt.config is not wt.repo.config
    assert wt.config['core.bare'].value is False
    assert wt.path == gitrepo
    assert wt.repo.path != wt.path

    # test resolve to root
    test_path = wt.path / 'subdir'
    test_path.mkdir()
    wt_sub = Worktree(test_path)
    assert wt_sub.path == wt.path
    # and actually
    assert wt_sub is wt


def test_work_error(tmp_path):
    err_match = 'not point to an existing Git worktree/checkout'
    with pytest.raises(ValueError, match=err_match):
        Worktree(tmp_path)
    with pytest.raises(ValueError, match=err_match):
        Worktree(tmp_path / 'notexist')
    test_file = tmp_path / 'afile'
    test_file.touch()
    with pytest.raises(ValueError, match=err_match):
        Worktree(test_file)


def test_secondary_worktree(tmp_path, gitrepo):
    test_key = 'brand.new.key'
    test_key2 = 'other.brand.new.key'
    branch = 'dummy'
    wt_path = tmp_path / branch
    call_git(
        [
            '-C',
            str(gitrepo),
            'worktree',
            'add',
            str(wt_path),
        ]
    )
    wt1 = Worktree(gitrepo)
    wt2 = Worktree(wt_path)
    # and the repo is represented by the very same instance
    assert wt1.repo is wt2.repo
    # but all config managers are slightly different
    assert wt1.config is not wt2.config
    assert wt1.config is not wt1.repo.config

    # now enable a dedicated worktree config
    wt1.config.sources['git-local'][
        # we use snake casing here. the section/variable
        # name is case-insensitive, and it must not matter
        'extensions.worktreeConfig'
    ] = ConfigItem('true')
    wt1.enable_worktree_config()
    # we have to enable it for all linked worktrees manually.
    # the alternative would be a complex search/tracking of
    # related worktree instances, or a continuous on-access
    # reevalutation. Both are not worth the trouble, given that
    # such setup changes are presumbably rare
    wt2.enable_worktree_config()
    # and run it again, just to see that it does no harm
    wt2.enable_worktree_config()
    # and the repo is represented by the very same instance
    assert wt1.repo is wt2.repo
    # but the worktree config is no longer the same
    assert wt1.config is not wt2.config
    # setting the same key with different value in both worktrees
    wt1.config.sources['git-worktree'][test_key] = ConfigItem('wt1')
    wt2.config.sources['git-worktree'][test_key] = ConfigItem('wt2')
    assert wt1.config[test_key].value == 'wt1'
    assert wt2.config[test_key].value == 'wt2'
    # wt2's worktree scope is not "chained" after wt1, there is just
    # the one setting we found above
    assert len(wt2.config.getall(test_key)) == 1
    wt2.config.sources['git-worktree'].reinit().load()
    assert len(wt2.config.getall(test_key)) == 1
    # only set through the main worktree, but into the shared local scope
    assert test_key2 not in wt1.config
    assert test_key2 not in wt2.config
    wt1.config.sources['git-local'][test_key2] = ConfigItem('shared')
    assert test_key2 in wt1.config
    assert test_key2 in wt2.config

    # check that we can use Repo/Worktree objects as dict keys
    # (e.g. to group some results by repo/worktree)
    rwd = {
        wt1: 'wt1',
        wt2: 'wt2',
        wt1.repo: 'repo',
    }
    assert rwd[wt1] == 'wt1'
    assert rwd[wt2] == 'wt2'
    assert rwd[wt1.repo] == 'repo'


def test_worktree_init_at(tmp_path):
    # only existing directories
    with pytest.raises((FileNotFoundError, NotADirectoryError)):
        Worktree.init_at(tmp_path / 'nothere')

    orig_wt_path = tmp_path / 'orig_wt'
    orig_wt_path.mkdir()
    orig_wt = Worktree.init_at(orig_wt_path)
    assert orig_wt.path == orig_wt_path.absolute()
    # cursory test that the repo is functional
    assert orig_wt.repo.config['core.bare'].value is False
    assert orig_wt.config['core.bare'].value is False

    # init alternative worktree. This is not a "linked" worktree.
    # instead this merely points to the same repository. changes
    # made in this worktree will cause unsynchronized differences
    # at `orig_wt`. Likely not a use case, but we are testing the
    # proper functioning of the mechanics anyways
    alt_wt_path = tmp_path / 'alt_wt'
    alt_wt_path.mkdir()
    alt_wt = Worktree.init_at(alt_wt_path, gitdir=orig_wt.repo.path)
    assert alt_wt.path == alt_wt_path.absolute()
    assert alt_wt.config['core.bare'].value is False
    assert orig_wt.repo is alt_wt.repo

    # try relocating the repository of a worktree
    sep_wt_path = tmp_path / 'sep_wt'
    sep_wt_path.mkdir()
    sep_repo_path = tmp_path / 'sep_repo'
    sep_repo_path.mkdir()
    sep_wt = Worktree.init_at(sep_wt_path, gitdir=sep_repo_path)
    assert sep_wt.config['core.bare'].value is False
    # relocate
    assert sep_repo_path.is_dir()
    # keep ref for testing
    sep_repo_old = sep_wt.repo
    sep_repo_path_new = tmp_path / 'sep_repo_new'
    sep_wt_new = Worktree.init_at(sep_wt_path, gitdir=sep_repo_path_new)
    assert sep_wt_new is sep_wt
    assert not sep_repo_path.is_dir()
    # we got a new instance for the repo
    assert sep_wt.repo is not sep_repo_old
    assert sep_wt.repo.path == sep_repo_path_new


def test_secondary_worktree_w_annex(tmp_path, annexrepo):
    wt1 = Worktree(annexrepo)
    test_content = 'mycontent'
    test_file_name = 'myfile.dat'
    test_file = wt1.path / test_file_name
    test_file.write_text(test_content)
    call_git(['-C', str(wt1.path), 'annex', 'add', str(test_file)])
    call_git(['-C', str(wt1.path), 'commit', '-m', 'annexed file'])

    branch = 'dummy'
    wt2_path = tmp_path / branch
    call_git(
        [
            '-C',
            str(annexrepo),
            'worktree',
            'add',
            str(wt2_path),
        ]
    )
    wt2 = Worktree(wt2_path)
    assert wt2.annex is not None
    # verifies implicitly that git-annex-info work in both worktrees
    assert wt1.annex.uuid == wt2.annex.uuid

    for wt in (wt1, wt2):
        # annex-getting the content is needed for robustness, not all
        # platforms have immediately usable symlinks to the annex
        list(call_annex_json_lines(
            ['get', test_file_name],
            git_args=['-C', str(wt.annex.path)],
        ))
        assert (wt.path / test_file_name).read_text() == test_content
