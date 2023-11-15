from middlewared.test.integration.utils import call


def test_sysctl_arc_max_is_set():
    """Middleware should have set this value early in boot phase
    and this should return a number"""
    assert call('sysctl.get_default_arc_max')
