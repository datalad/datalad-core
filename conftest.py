"""Fixture setup"""

__all__ = [
    'cfgman',
    'bareannexrepo',
    'baregitrepo',
    'annexrepo',
    'gitrepo',
    'verify_pristine_gitconfig_global',
]


from datalad_core.tests.fixtures import (
    # function-scope temporary Git repo with an initialized annex
    annexrepo,
    # function-scope temporary, bare Git repo with an initialized annex
    bareannexrepo,
    # function-scope temporary, bare Git repo
    baregitrepo,
    # function-scope config manager
    cfgman,
    # function-scope temporary Git repo
    gitrepo,
    # verify no test leave contaminated config behind
    verify_pristine_gitconfig_global,
)
