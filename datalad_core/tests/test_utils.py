from datalad_core.runners import call_git
from datalad_core.tests.utils import modify_dataset


def test_modify_dataset(gitrepo):
    promise = modify_dataset(gitrepo)
    assert promise == call_git(
        ['status', '-uall', '--porcelain=v1'],
        cwd=gitrepo,
        capture_output=True,
        text=True,
    )
