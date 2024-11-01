import pytest

from ..git import (
    CommandError,
    call_git,
    call_git_lines,
    call_git_oneline,
    call_git_success,
    iter_git_subproc,
)


def test_call_git():
    # by default no output is captured
    assert call_git(['--version']) is None
    # capture gives bytes unless text=True
    assert b'version' in call_git(['--version'], capture_output=True)
    assert 'version' in call_git(['--version'], text=True, capture_output=True)
    # raises properly
    with pytest.raises(CommandError):
        call_git(['notacommand'])


def test_call_git_success():
    assert call_git_success(['--version'])
    assert not call_git_success(['notacommand'])


def test_call_git_lines():
    lines = call_git_lines(['--version'], force_c_locale=True)
    assert len(lines) == 1
    assert lines[0].startswith('git version')
    # check that we can force Git into LC_ALL mode.
    # this test is only meaningful on systems that
    # run with some other locale
    call_git_lines(['-h'])[0].casefold().startswith('usage')


def test_call_git_oneline():
    line = call_git_oneline(['--version'])
    assert line.startswith('git version')
    # raise when there is more than oneline
    with pytest.raises(AssertionError):
        call_git_oneline(['rev-parse', '--git-dir', '--git-common-dir'])
    # raise when there is no line
    with pytest.raises(AssertionError):
        call_git_oneline(
            ['stripspace'],
            inputs='',
        )


def test_iter_git_subproc():
    # just a smoke test that 'git' gets prepended
    with iter_git_subproc(['--version']) as g:
        assert list(g)
