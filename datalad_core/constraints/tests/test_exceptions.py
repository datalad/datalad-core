from datalad_core.constraints.exceptions import ConstraintError

fake_constraint = None
value_placeholder = 'noint'
msg_placefolder = 'yeah, {__value__!r} is stupid. Why?\n{__itemized_causes__}'
msg_placefolder_nocause = 'yeah, {__value__!r} is stupid'
cause_placeholder = RuntimeError('too went south quickly')
ctx_placeholder = {'__caused_by__': cause_placeholder}
error_init_args = (fake_constraint, value_placeholder, msg_placefolder, ctx_placeholder)
error_init_args_noctx = (fake_constraint, value_placeholder, msg_placefolder_nocause)


def test_constrainterror():
    ce = ConstraintError(*error_init_args)
    assert ce.constraint is fake_constraint


def test_constrainterror_repr():
    ce = ConstraintError(*error_init_args)
    assert repr(ce) == (
        f'ConstraintError({fake_constraint!r}, {value_placeholder!r}, '
        f'{msg_placefolder!r}, {ctx_placeholder!r})'
    )
    assert (
        ce.msg
        == str(ce)
        == msg_placefolder.format(
            __value__=value_placeholder, __itemized_causes__=f'  - {cause_placeholder}'
        )
    )


def test_constrainterror_repr_noctx():
    ce = ConstraintError(*error_init_args_noctx)
    assert (
        ce.msg == str(ce) == msg_placefolder_nocause.format(__value__=value_placeholder)
    )


def test_constrainterror_repr_multiexception():
    ce = ConstraintError(
        *error_init_args[:-1],
        {'__caused_by__': (cause_placeholder, RuntimeError('even more cause'))},
    )
    assert (
        ce.msg
        == str(ce)
        == msg_placefolder.format(
            __value__=value_placeholder,
            __itemized_causes__=(f'  - {cause_placeholder}\n' f'  - even more cause'),
        )
    )
