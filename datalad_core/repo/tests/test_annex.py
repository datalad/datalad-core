import pytest

from datalad_core.runners import (
    CommandError,
)

from ..annex import (
    Annex,
    BareRepoAnnex,
)
from ..repo import Repo
from ..worktree import Worktree


def test_barerepoannex_error(baregitrepo):
    with pytest.raises(ValueError, match='no repository annex found'):
        BareRepoAnnex(baregitrepo)


def test_barerepoannex_nonbare(annexrepo):
    with pytest.raises(ValueError, match='not a bare repository'):
        BareRepoAnnex(annexrepo)

    wt = Worktree(annexrepo)
    with pytest.raises(TypeError, match='Cannot initialize annex in a non-bare repo'):
        wt.repo.init_annex()

    assert wt.repo.bare_annex is None


def test_annex_error(annexrepo):
    with pytest.raises(ValueError, match='cannot resolve path'):
        Annex(Worktree(annexrepo).git_dir)


def test_annex_noannex(gitrepo):
    with pytest.raises(ValueError, match='no repository annex found'):
        Annex(gitrepo)

    wt = Worktree(gitrepo)
    assert wt.annex is None
    # and it keeps it that way on repeated trials
    assert wt.annex is None


def test_annex(annexrepo):
    annex0 = Annex(annexrepo)
    # initialization is robust to "anywhere in repo"
    testdir = annexrepo / 'somedir'
    testdir.mkdir()
    annex1 = Annex(testdir)
    assert annex0.path == annex1.path == annexrepo
    assert annex0.uuid


def test_repo_init_annex_error(baregitrepo):
    repo = Repo(baregitrepo)
    # we take the place of the annex
    (repo.path / 'annex').touch()
    with pytest.raises(
        CommandError, match='fileExist|file already exists|Not a directory'
    ):
        repo.init_annex()


def test_worktree_init_annex(gitrepo):
    wt = Worktree(gitrepo)
    annex = wt.init_annex()
    assert wt.annex is annex
    assert wt.annex.uuid


def test_repo_init_annex(baregitrepo):
    repo = Repo(baregitrepo)
    assert repo.bare_annex is None

    # setting the flag has no effect here, it just exercises the
    # code path
    annex = repo.init_annex('testannex', autoenable_remotes=False)
    assert annex is repo.bare_annex
    assert repo.bare_annex.uuid
    # ask again to exercise cached code path
    assert repo.bare_annex.uuid


def test_relocate_repo_w_annex(tmp_path):
    wt_dir = tmp_path / 'wt'
    orig_repo_dir = tmp_path / 'orig_repo'
    new_repo_dir = tmp_path / 'new_repo'

    wt_dir.mkdir()

    wt = Worktree.init_at(wt_dir, gitdir=orig_repo_dir)
    wt.init_annex()
    assert wt.repo.path == orig_repo_dir
    # annex commands run in the context of the worktree, not the repo
    assert wt.annex.path == wt.path
    annexes = wt.annex.list_annexes()
    assert len(annexes) > 1

    wt_new = Worktree.init_at(wt_dir, gitdir=new_repo_dir)
    assert wt_new.repo.path == new_repo_dir
    assert (new_repo_dir / 'annex').is_dir()
    assert wt_new.annex.path == wt.path
    # running annex commands continues to work after relocation
    assert annexes == wt_new.annex.list_annexes()
