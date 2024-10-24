import pytest

from datalad_core.constraints.basic import (
    EnsureChoice,
    EnsureMappingtHasKeys,
    NoConstraint,
)
from datalad_core.constraints.exceptions import ConstraintError


def test_noconstraint():
    c = NoConstraint()
    assert not c.input_synopsis
    test_val = 5
    assert c(test_val) is test_val


def test_ensurechoice():
    c = EnsureChoice('choice1', 'choice2', None)
    assert c.input_synopsis == "one of {'choice1','choice2',None}"
    assert str(c) == f'Constraint[{c.input_synopsis}]'
    # this should always work
    assert c('choice1') == 'choice1'
    assert c(None) is None
    # this should always fail
    with pytest.raises(ValueError, match='is not one of'):
        c('fail')
    with pytest.raises(ValueError, match='is not one of'):
        c('None')


def test_ensuremappinghaskeys():
    c = EnsureMappingtHasKeys(())
    assert c.input_synopsis == 'mapping'
    with pytest.raises(ConstraintError, match='not a mapping'):
        c(5)
    test_mapping = {5: 'some', 'A': 'some', None: 'some'}
    assert c(test_mapping) is test_mapping

    c = EnsureMappingtHasKeys((None, 5))
    assert c(test_mapping) is test_mapping

    c = EnsureMappingtHasKeys(('exotic', 'bogus'))
    with pytest.raises(ConstraintError, match='missing.*exotic.*bogus'):
        c(test_mapping)
