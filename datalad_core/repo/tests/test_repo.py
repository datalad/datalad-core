from shutil import rmtree

from ..repo import Repo


def test_repo(baregitrepo):
    repo = Repo(baregitrepo)
    assert str(repo) == f'Repo({baregitrepo})'
    assert repr(repo) == f'Repo({baregitrepo!r})'

    assert repo.config['core.bare'].value is True
    # do again to test cached retrieval (partial coverage)
    assert repo.config['core.bare'].value is True

    assert repo.path is baregitrepo
    assert repo.git_dir == baregitrepo
    assert repo.git_common_dir == baregitrepo
    # and again for the cached retrieval
    assert repo.git_dir == baregitrepo
    assert repo.git_common_dir == baregitrepo


def test_repo_vanish(baregitrepo):
    repo = Repo(baregitrepo)
    assert repo.flyweight_valid()
    rmtree(baregitrepo)
    assert not repo.flyweight_valid()
