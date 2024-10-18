import pytest

from datalad_core.commands import Dataset
from datalad_core.constraints.constraint import (
    AllOf,
    Constraint,
)
from datalad_core.constraints.exceptions import ConstraintError


class IsTrue(Constraint):
    input_synopsis = 'must be `True`'
    input_description = 'long-form of saying: it must be `True`'

    def __call__(self, value):
        if value is not True:
            self.raise_for(value, '{__value__} is not True')
        return True


class Equals5(Constraint):
    input_synopsis = 'must be `5`'
    input_description = 'long-form of saying: it must be `5`'

    def __call__(self, value):
        if value != 5:  # noqa: PLR2004
            self.raise_for(value, '{__value__} is not 5')
        return value


class EnsureInt(Constraint):
    input_synopsis = 'must be convertible to type INT'
    input_description = 'long-form of saying: it must be convertible to type INT'

    def __call__(self, value):
        try:
            return int(value)
        except ValueError as e:
            self.raise_for(
                value,
                '{__value__} is not convertible to INT',
                __caused_by__=e,
            )


def test_constraint_basics():
    c = IsTrue()
    assert str(c) == f'Constraint[{IsTrue.input_synopsis}]'
    assert repr(c) == f'{c.__class__.__name__}()'
    assert c(True) is True
    with pytest.raises(ConstraintError, match='False is not True') as e:
        c(False)
    # first value is the exception
    assert e.value.value is False


def test_constraint_anyof():
    # logical OR
    c = IsTrue()
    eq5 = Equals5()
    true_or_5 = c | eq5
    assert str(true_or_5) == f'Constraint[{c.input_synopsis} or {eq5.input_synopsis}]'
    assert repr(true_or_5) == f'{true_or_5.__class__.__name__}({c!r}, {eq5!r})'
    assert true_or_5(True) is True
    assert true_or_5(5) == 5  # noqa: PLR2004
    assert true_or_5(5.0) == 5.0  # noqa: PLR2004
    with pytest.raises(ConstraintError, match='False is not True'):
        true_or_5(False)
    with pytest.raises(ConstraintError, match='not match any of 2'):
        true_or_5('five')

    # we can chain AnyOf, and we get no nesting
    true_or_5_or_int = true_or_5 | EnsureInt()
    assert len(true_or_5_or_int.constraints) == len(true_or_5.constraints) + 1
    # also works with AnyOf and AnyOf
    monster = true_or_5 | true_or_5_or_int
    # it just merges the lists, this is inelegant but still correct
    assert len(monster.constraints) == len(true_or_5.constraints) + len(
        true_or_5_or_int.constraints
    )

    # somehow both descriptions are in there. we do not test further, because
    # the current implementation is not sufficient anyways
    assert c.input_description in true_or_5.input_description
    assert eq5.input_description in true_or_5.input_description


def test_constraint_allof():
    # logical AND
    int5 = EnsureInt() & Equals5()
    assert isinstance(int5('5'), int)
    assert int5('5') == 5  # noqa: PLR2004
    with pytest.raises(ConstraintError, match='five is not convertible to INT'):
        int5('five')

    # test corner of of an AllOf of a single one
    eq5 = Equals5()
    aoeq5 = AllOf(eq5)
    assert str(aoeq5) == str(eq5)

    # check merge rules work out, chaining, not nesting
    assert len((aoeq5 & eq5).constraints) == len(aoeq5.constraints) + 1
    assert len((aoeq5 & int5).constraints) == len(aoeq5.constraints) + len(
        int5.constraints
    )

    # somehow both descriptions are in there. we do not test further, because
    # the current implementation is not sufficient anyways
    assert EnsureInt().input_description in int5.input_description
    assert eq5.input_description in int5.input_description


def test_constraint_for_dataset():
    class BecomesB(Constraint):
        input_synopsis = 'B'

        def __call__(self, value):  # noqa: ARG002
            return 'B'

    class WeirdOne(Constraint):
        input_synopsis = 'shapeshifter'

        def __call__(self, value):  # noqa: ARG002
            return 'A'

        def for_dataset(self, dataset):  # noqa: ARG002
            return BecomesB()

    c1 = WeirdOne()
    assert c1('anything') == 'A'
    c2 = c1.for_dataset(Dataset(None))
    assert c2.input_description == 'B'
    assert c2('anything') == 'B'

    # same when put into a MultiConstraint
    ca = AllOf(WeirdOne())
    assert ca('anything') == 'A'
    cb = ca.for_dataset(Dataset(None))
    assert cb('anything') == 'B'

    # without a dedicated implementation there is no transformation
    c = BecomesB()
    assert c.for_dataset(Dataset(None)) is c
