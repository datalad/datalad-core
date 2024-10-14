import pytest

from .. import CommandError
from ..annex import call_annex_json_lines

# we do not want to afford the more_itertools dependency at this point.
# we nevertheless want to clarity
consume = list


def test_call_annex_json_lines(tmp_path, bareannexrepo):
    # does not hide fundamental errors
    with pytest.raises((FileNotFoundError, NotADirectoryError)):
        consume(call_annex_json_lines(['info'], cwd=tmp_path / 'nothere'))
    with pytest.raises(CommandError, match='cannot change to'):
        consume(call_annex_json_lines(['info'], git_args=['-C', tmp_path / 'nothere']))
    with pytest.raises(CommandError, match='Not in a git repo'):
        consume(call_annex_json_lines(['info'], cwd=tmp_path))

    # simple test: 'gitannex-info' yields only a single JSON line.
    # primarily checks the function parameters
    res1 = list(call_annex_json_lines(['info'], cwd=bareannexrepo))
    # same as above, but use gitargs to change to the repo dir
    res2 = list(call_annex_json_lines(['info'], git_args=['-C', str(bareannexrepo)]))
    assert len(res1) == len(res2)
    res1 = res1[0]
    res2 = res2[0]
    # strip volatile properties
    for r in (res1, res2):
        r.pop('available local disk space')
    assert res1 == res2
    res = res1
    # we get a fully decodes structure back (value is an int)
    assert res['local annex keys'] == 0
    # standard keys
    assert res['success'] is True
    assert res['error-messages'] == []
    assert res['command'] == 'info'

    local_root = '.'
    local_remote = 'here'
    res = list(
        call_annex_json_lines(['info', local_root, local_remote], cwd=bareannexrepo)
    )
    # we get one result per request
    assert len(res) == len((local_root, local_remote))
    # order matches
    assert res[0]['input'] == [local_root]
    assert res[1]['input'] == [local_remote]


def test_call_annex_json_lines_multierrors(annexrepo):
    with pytest.raises(CommandError, match='2 errors.*not a directory'):
        consume(call_annex_json_lines(['info', 'absent', 'gone'], cwd=annexrepo))
