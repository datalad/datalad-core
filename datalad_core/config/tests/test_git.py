import pytest

from datalad_core.consts import DATALAD_BRANCH_CONFIG_RELPATH
from datalad_core.runners import call_git_oneline

from ..git import (
    DataladBranchConfig,
    GlobalGitConfig,
    LocalGitConfig,
)
from ..item import ConfigurationItem


@pytest.mark.usefixtures('cfgman')
def test_global_git_config():
    target_key = 'my.config.key'
    target_value = 'my/config.value'

    gc = GlobalGitConfig()
    gc[target_key] = ConfigurationItem(value=target_value)
    # immediate availability
    assert target_key in gc
    assert gc[target_key].value == target_value

    # if we create another instance, it also has the key, because
    # we wrote to a file, not just the instance
    gc2 = GlobalGitConfig()
    assert target_key in gc2
    assert gc2[target_key].value == target_value

    assert 'user.email' in gc
    assert gc['user.email']

    addon_key = 'test.addon'
    addon_items = (ConfigurationItem('one'), ConfigurationItem('two'))
    gc.add(addon_key, addon_items[0])
    gc.add(addon_key, addon_items[1])
    assert gc.getall(addon_key) == addon_items


def test_global_git_config_pure(cfgman):
    orig_keys = GlobalGitConfig().keys()
    with cfgman.overrides(
        {
            'datalad.absurdkey': ConfigurationItem('absurddummy'),
        }
    ):
        # check that the comamnd-scope configuration does not bleed
        # into the global scope (global here being an example for any
        # other scope)
        assert GlobalGitConfig().keys() == orig_keys
        # but Git does see the manipulation
        assert call_git_oneline(['config', 'datalad.absurdkey']) == 'absurddummy'


def test_local_git_config_norepo(tmp_path):
    with pytest.raises(ValueError, match='no Git repository at'):
        LocalGitConfig(tmp_path)


def test_local_git_config(gitrepo):
    lc = LocalGitConfig(gitrepo)
    lc.load()
    # check something we would expect under all circumstances
    assert lc['core.bare'].value == 'false'


def test_datalad_branch_config(gitrepo):
    dbc = DataladBranchConfig(gitrepo)
    cfgfile = gitrepo / DATALAD_BRANCH_CONFIG_RELPATH
    assert not cfgfile.exists()
    # must not fail, even when there is no branch config
    dbc.load()
    assert len(dbc) == 0
    test_key = 'datalad.some.key'
    test_value = ConfigurationItem('irrelevant')
    test_value2 = ConfigurationItem('alsoirrelevant')
    dbc[test_key] = test_value
    assert cfgfile.exists()
    assert 'key = irrelevant' in cfgfile.read_text()
    dbc.add(test_key, test_value2)
    assert 'key = irrelevant' in cfgfile.read_text()
    assert 'key = alsoirrelevant' in cfgfile.read_text()
    assert dbc.getall(test_key) == (test_value, test_value2)

    state_backup = {k: dbc[k] for k in dbc}
    dbc.reinit().load()
    assert state_backup == {k: dbc[k] for k in dbc}


def test_datalad_branch_shorthand(gitrepo):
    dbc = DataladBranchConfig(gitrepo)
    cfgfile = gitrepo / DATALAD_BRANCH_CONFIG_RELPATH
    cfgfile.parent.mkdir()
    cfgfile.write_text('[shorthand]\n\tenabled\n')
    dbc.load()
    assert dbc['shorthand.enabled'].value == 'true'
