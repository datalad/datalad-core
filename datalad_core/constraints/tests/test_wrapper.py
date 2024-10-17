import pytest

from ..constraint import Constraint
from ..exceptions import ConstraintError
from ..wrapper import WithDescription


class IsTrue(Constraint):
    input_synopsis = 'must be `True`'
    input_description = 'long-form of saying: it must be `True`'

    def __call__(self, value):
        if value is not True:
            self.raise_for(value, '{__value__} is not True')
        return True


def test_withdescription():
    c = IsTrue()
    # it is possible, albeit pointless, to not replace any description
    d = WithDescription(c)
    assert str(d) == str(c)

    input_synopsis = 'must be True in this empire'
    input_description = "bISeH'eghlaH'be'chugh latlh Dara'laH'be'"
    error_message = '{__value__!r} has no honor'

    d = WithDescription(
        c,
        input_synopsis=input_synopsis,
        input_description=input_description,
        error_message=error_message,
    )
    assert repr(d) == (
        f'WithDescription({c!r}, '
        f'input_synopsis={input_synopsis!r}, '
        f'input_description={input_description!r}, '
        # "input_synopsis_for_ds='dssynopsis', "
        # "input_description_for_ds='dsdescription', "
        f'error_message={error_message!r}'
        # "error_message_for_ds='dserror')"
        ')'
    )

    assert d.input_description == input_description

    # the wrapped constraint looks like and unwrapped one
    assert str(d) == f'Constraint[{input_synopsis}]'
    with pytest.raises(ConstraintError) as e:
        d(5)
    assert e.value.msg == error_message.format(__value__=5)
    assert d(True) is True
