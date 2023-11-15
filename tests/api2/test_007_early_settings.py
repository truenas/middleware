from middlewared.test.integration.utils import call
from middlewared.plugins.sysctl.sysctl_info import DEFAULT_ARC_MAX_FILE


def test_sysctl_arc_max_is_set():
    """Middleware should have created this file and written a number
    to it early in the boot process. That's why we check it here in
    this test so early"""
    assert call('filesystem.stat', DEFAULT_ARC_MAX_FILE)['size']
