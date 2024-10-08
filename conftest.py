"""Fixture setup"""

__all__ = [
    'cfgman',
    'baregitrepo',
    'gitrepo',
    'verify_pristine_gitconfig_global',
]


from datalad_core.tests.fixtures import (
    # function-scope temporary, bare Git repo
    baregitrepo,
    # function-scope config manager
    cfgman,
    # function-scope temporary Git repo
    gitrepo,
    # verify no test leave contaminated config behind
    verify_pristine_gitconfig_global,
)
