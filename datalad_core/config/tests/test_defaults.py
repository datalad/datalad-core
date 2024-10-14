import pytest

from ..defaults import (
    anything2bool,
    get_defaults,
)


def test_implementationdefaults():
    df = get_defaults()
    assert str(df) == 'ImplementationDefaults'


def test_anything2bool():
    for f in ('', None, 'Off', 'OFF', 'off', 'no', 'false', '0', False):
        assert anything2bool(f) is False
    for t in ('On', 'ON', 'on', 'yes', 'true', '1', 2, True):
        assert anything2bool(t) is True
    with pytest.raises(ValueError, match='Cannot interpret'):
        anything2bool('broken')
