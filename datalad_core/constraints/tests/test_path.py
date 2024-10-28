from pathlib import (
    Path,
    PurePath,
)

import pytest

from datalad_core.commands import Dataset
from datalad_core.constraints import ConstraintError
from datalad_core.repo import Worktree

from ..path import EnsurePath


def test_EnsurePath_nopath():
    c = EnsurePath()
    with pytest.raises(ConstraintError, match='not.*int'):
        c(5)


def test_EnsurePath(tmp_path):
    target = Path(tmp_path)

    assert EnsurePath()(tmp_path) == target
    assert EnsurePath(lexists=True)(tmp_path) == target
    with pytest.raises(ConstraintError):
        EnsurePath(lexists=False)(tmp_path)
    with pytest.raises(ConstraintError):
        EnsurePath(lexists=True)(tmp_path / 'nothere')
    assert EnsurePath(is_format='absolute')(tmp_path) == target
    with pytest.raises(ConstraintError):
        EnsurePath(is_format='relative')(tmp_path)
    with pytest.raises(ConstraintError):
        EnsurePath(is_format='absolute')(tmp_path.name)
    from stat import S_ISDIR, S_ISREG

    assert EnsurePath(is_mode=S_ISDIR)(tmp_path) == target
    with pytest.raises(ConstraintError):
        EnsurePath(is_mode=S_ISREG)(tmp_path)
    # give particular path type
    assert EnsurePath(path_type=PurePath)(tmp_path) == PurePath(tmp_path)
    # not everything is possible, this is known and OK
    with pytest.raises(ConstraintError, match='cannot check mode'):
        EnsurePath(
            path_type=PurePath,
            is_mode=S_ISREG,
        )(tmp_path)
    assert EnsurePath().input_synopsis == 'path'
    assert EnsurePath(is_format='absolute').input_synopsis == 'absolute path'
    # default comparison mode is parent-or-same-as
    c = EnsurePath(ref=target)
    assert c(target) == target
    assert c(target / 'some') == target / 'some'
    with pytest.raises(ConstraintError):
        assert c(target.parent)
    c = EnsurePath(ref=target, ref_is='parent-of')
    assert c(target / 'some') == target / 'some'
    with pytest.raises(ConstraintError):
        assert c(target)
    assert c.input_synopsis == f'path that is parent-of {target}'
    with pytest.raises(ValueError, match='unrecognized'):
        c = EnsurePath(ref=target, ref_is='stupid')


def test_EnsurePath_fordataset(gitrepo):
    test_relpath = Path('relpath')
    # standard: relative in, relative out
    c = EnsurePath()
    assert c('relpath') == test_relpath
    # tailor constraint for our dataset
    # (this is what would be done by EnsureCommandParameterization
    # 1. dataset given as a path -- resolve against CWD
    #    output is always absolute
    tc = c.for_dataset(Dataset(gitrepo))
    # the description stays the same
    assert c.input_synopsis == tc.input_synopsis
    assert tc('relpath') == test_relpath
    # 2. dataset is given as a worktree object
    tc = c.for_dataset(Dataset(Worktree(gitrepo)))
    assert tc('relpath') == (gitrepo / 'relpath')
    # no change for any absolute path
    assert tc(Path.cwd()) == Path.cwd()

    # returns the dataset path for `None`
    assert tc(None) == gitrepo
