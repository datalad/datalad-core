from os import environ

import pytest

from datalad_core.config import get_manager
from datalad_core.repo import (
    Repo,
    Worktree,
)


def test_manager_setup():
    """Test the actual global configuration manager"""
    manager = get_manager()
    target_sources = [
        'git-command',
        'git-global',
        'git-system',
        'defaults',
    ]
    target_key = 'user.name'
    absurd_must_be_absent_key = 'nobody.would.use.such.a.key'
    # the order of sources is the precedence rule
    assert list(manager.sources.keys()) == target_sources
    # any real manager will have some keys
    assert len(manager)
    assert target_key in manager
    assert absurd_must_be_absent_key not in manager
    # test query
    item = manager[target_key]
    with pytest.raises(KeyError):
        manager[absurd_must_be_absent_key]
    # we cannot be really specific and also robust
    assert item.value
    assert manager[target_key]
    assert manager.get(absurd_must_be_absent_key).value is None

    with pytest.raises(TypeError):
        del manager.sources['git-system']
    with pytest.raises(TypeError):
        manager.sources['new'] = manager.sources['defaults']


def test_manager_overrides():
    manager = get_manager()
    test_key = 'test_manager_overrides.test_key'
    target_key_env = 'GIT_CONFIG_KEY_0'
    target_val_env = 'GIT_CONFIG_VALUE_0'
    try:
        # we need at least one item posted to the environment for
        # this test. this is done next, and taken out again in
        # finally.
        manager.sources['git-command'][test_key] = manager.item_type('irrelevant')
        # we don't care what is KEY_0 at this point, but there should be some
        # capture whatever it is
        orig_key_name = environ[target_key_env]
        orig_key_value = environ[target_val_env]
        assert orig_key_name
        with manager.overrides(
            {
                orig_key_name: manager.item_type('alsoirrelevant'),
                'smoketest.for.tuple': (
                    manager.item_type('ping'),
                    manager.item_type('pong'),
                ),
            }
        ):
            assert environ[target_val_env] != orig_key_value
        # after context manager exit we find things restored
        assert environ[target_key_env] == orig_key_name
        assert environ[target_val_env] == orig_key_value
    finally:
        del manager.sources['git-command'][test_key]


def test_manager_fordataset(gitrepo):
    # base manager, not dataset-specific
    manager = get_manager()
    repo = Worktree(gitrepo).repo
    dm = repo.config
    for s in ['git-system', 'git-global', 'git-command']:
        assert manager.sources[s] is dm.sources[s]
    assert 'datalad-branch' not in manager.sources
    assert 'datalad-branch' in dm.sources
    assert 'git-local' in dm.sources
    assert 'core.bare' in dm
    assert dm['core.bare'].value is False


def test_manager_forbaredataset(baregitrepo):
    dm = Repo(baregitrepo).config
    assert dm['core.bare'].value is True
