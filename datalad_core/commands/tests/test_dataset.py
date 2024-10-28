from pathlib import Path

import pytest

from datalad_core.commands.dataset import (
    Dataset,
    EnsureDataset,
)
from datalad_core.config import ConfigItem
from datalad_core.constraints import ConstraintError
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


def test_ensuredataset(tmp_path):
    assert EnsureDataset().input_synopsis == '(path to) a dataset'
    assert (
        EnsureDataset(installed=True).input_synopsis == '(path to) an existing dataset'
    )
    assert (
        EnsureDataset(installed=False).input_synopsis
        == '(path to) a non-existing dataset'
    )

    with pytest.raises(
        ConstraintError,
        match="cannot create Dataset from <class 'int'>",
    ):
        EnsureDataset()(5)

    with pytest.raises(
        ConstraintError,
        match='not installed',
    ):
        EnsureDataset(installed=True)(tmp_path)


def test_ensuredataset_bare(baregitrepo):
    c = EnsureDataset()
    for spec in (baregitrepo,):
        assert c(spec).repo.path == baregitrepo

    with pytest.raises(
        ConstraintError,
        match='already exists locally',
    ):
        EnsureDataset(installed=False)(baregitrepo)


def test_ensuredataset_nonbare(gitrepo):
    c = EnsureDataset()
    for spec in (gitrepo,):
        assert c(spec).worktree.path == gitrepo

    with pytest.raises(
        ConstraintError,
        match='already exists locally',
    ):
        EnsureDataset(installed=False)(gitrepo)


def test_ensuredataset_with_id(tmp_path, gitrepo):
    c = EnsureDataset(installed='with-id')
    with pytest.raises(
        ConstraintError,
        match='not installed',
    ):
        c(tmp_path)

    with pytest.raises(
        ConstraintError,
        match='does not have a datalad-id',
    ):
        c(gitrepo)

    # now set an ID in the branch config and satisfy the test
    wt = Worktree(gitrepo)
    wt.config.sources['datalad-branch']['datalad.dataset.id'] = ConfigItem(
        '9557edc6-910e-11ef-bcf8-23e60847c95d'
    )
    assert c(gitrepo).path == gitrepo
