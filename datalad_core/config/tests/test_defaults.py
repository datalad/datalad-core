from ..defaults import get_defaults


def test_implementationdefaults():
    df = get_defaults()
    assert str(df) == 'ImplementationDefaults'
