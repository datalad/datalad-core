from datalad_core.constraints.basic import NoConstraint


def test_noconstraint():
    c = NoConstraint()
    assert not c.input_synopsis
    test_val = 5
    assert c(test_val) is test_val
