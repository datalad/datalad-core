from pathlib import Path

from datalad_core.commands.dataset import Dataset
from datalad_core.repo import (
    Repo,
    Worktree,
)


def test_nonexisting_dataset_from_nothing():
    spec = None
    ds = Dataset(spec)
    _assert_no_underlying_git(spec, ds)
    assert ds.path == Path.cwd()


def test_nonexisting_dataset_from_str():
    spec = 'whatever'
    ds = Dataset(spec)
    _assert_no_underlying_git(spec, ds)
    assert ds.path == Path(spec)


def test_nonexisting_dataset_from_path():
    spec = Path('whatever')
    ds = Dataset(spec)
    _assert_no_underlying_git(spec, ds)
    assert ds.path is spec


def test_existing_dataset_from_worktree(gitrepo):
    wt = Worktree(gitrepo)
    ds = Dataset(wt.path)
    assert ds.path == wt.path
    assert ds.worktree is wt
    assert ds.repo is wt.repo
    # cached retrieval
    assert ds.repo is wt.repo

    ds = Dataset(wt)
    assert ds.worktree is wt
    assert ds.repo is wt.repo

    ds = Dataset(wt.repo)
    assert ds.repo is wt.repo


def test_existing_dataset_from_barerepo(baregitrepo):
    repo = Repo(baregitrepo)
    ds = Dataset(repo.path)
    assert ds.path == repo.path
    assert ds.worktree is None
    assert ds.repo is repo
    # cached retrieval
    assert ds.repo is repo

    ds = Dataset(repo)
    assert ds.path == repo.path
    assert ds.worktree is None
    assert ds.repo is repo


def _assert_no_underlying_git(spec, ds):
    assert ds.pristine_spec is spec
    assert repr(ds) == f'Dataset({spec!r})'
    assert ds.repo is None
    assert ds.worktree is None
    # under all circumstances we have a path associated with a dataset
    assert ds.path is not None
