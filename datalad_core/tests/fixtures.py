"""Collection of fixtures for facilitation test implementations"""

from __future__ import annotations

from tempfile import NamedTemporaryFile
from typing import (
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

import pytest

from datalad_core.config import get_manager
from datalad_core.runners import call_git

magic_marker = 'c4d0de12-8008-11ef-86ea-3776083add61'
standard_gitconfig = f"""\
[datalad "magic"]
    test-marker = {magic_marker}
[user]
    name = DataLad Tester
    email = test@example.com
[extensions]
    worktreeConfig = false
"""


@pytest.fixture(autouse=False, scope='function')  # noqa: PT003
def cfgman(monkeypatch):
    """Yield a configuration manager with a test-specific global scope

    Any test using this fixture will be skipped for Git versions earlier
    than 2.32, because the `GIT_CONFIG_GLOBAL` environment variable used
    here was only introduced with that version.
    """
    manager = get_manager()
    ggc = manager.sources['git-global']
    with NamedTemporaryFile(
        'w',
        prefix='datalad_gitcfg_global_',
        delete=False,
    ) as tf:
        tf.write(standard_gitconfig)
        # we must close, because windows does not like the file being open
        # already when ConfigManager would open it for reading
        tf.close()
        with monkeypatch.context() as m:
            m.setenv('GIT_CONFIG_GLOBAL', tf.name)
            ggc = manager.sources['git-global']
            ggc.reinit()
            ggc.load()
            if (
                ggc['datalad.magic.test-marker'].pristine_value != magic_marker
            ):  # pragma: no cover
                pytest.skip(
                    'Cannot establish isolated global Git config scope '
                    '(possibly Git too old (needs v2.32)'
                )
            yield manager
    # reload to put the previous config in effect again
    ggc.reinit()
    ggc.load()


@pytest.fixture(autouse=True, scope='function')  # noqa: PT003
def verify_pristine_gitconfig_global():
    """No test must modify a user's global Git config.

    If such modifications are needed, a custom configuration setup
    limited to the scope of the test requiring it must be arranged.
    """
    from datalad_core.config import GlobalGitConfig

    def get_ggc_state():
        ggc = GlobalGitConfig()
        return {k: ggc[k].pristine_value for k in ggc}

    pre = get_ggc_state()
    yield
    if pre != get_ggc_state():  # pragma: no cover
        # this is hard to test, because we are inside an autoused fixture.
        # FWIW: this has been tested manually when it was implemented
        # originally
        msg = (
            'Global Git config modification detected. '
            'Test must be modified to use a temporary configuration target. '
            'Hint: use the `isolated_global_cfg` fixture.'
        )
        raise AssertionError(msg)


@pytest.fixture(autouse=False, scope='function')  # noqa: PT003
def gitrepo(tmp_path_factory) -> Generator[Path]:
    """Yield the path to an initialized Git repository"""
    # must use the factory to get a unique path even when a concrete
    # test also uses `tmp_path`
    path = tmp_path_factory.mktemp('gitrepo')
    call_git(
        ['init'],
        cwd=path,
        capture_output=True,
    )
    return path


@pytest.fixture(autouse=False, scope='function')  # noqa: PT003
def baregitrepo(tmp_path_factory) -> Generator[Path]:
    """Yield the path to an initialized, bare Git repository"""
    # must use the factory to get a unique path even when a concrete
    # test also uses `tmp_path`
    path = tmp_path_factory.mktemp('gitrepo')
    call_git(
        ['init', '--bare'],
        cwd=path,
        capture_output=True,
    )
    return path


@pytest.fixture(autouse=False, scope='function')  # noqa: PT003
def bareannexrepo(baregitrepo) -> Generator[Path]:
    """Yield the path to a bare Git repository with an initialized annex"""
    call_git(
        ['annex', 'init'],
        cwd=baregitrepo,
        capture_output=True,
    )
    return baregitrepo


@pytest.fixture(autouse=False, scope='function')  # noqa: PT003
def annexrepo(gitrepo) -> Generator[Path]:
    """Yield the path to a Git repository with an initialized annex"""
    call_git(
        ['annex', 'init'],
        cwd=gitrepo,
        capture_output=True,
    )
    return gitrepo
