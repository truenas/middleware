import pytest

from middlewared.test.integration.utils import call

# this is found in middlewared.plugins.sysctl.sysctl_info
# but the client running the tests isn't guaranteed to have
# the middlewared application installed locally
DEFAULT_ARC_MAX_FILE = '/var/run/middleware/default_arc_max'
pytestmark = pytest.mark.base

def test_sysctl_arc_max_is_set():
    """Middleware should have created this file and written a number
    to it early in the boot process. That's why we check it here in
    this test so early"""
    assert call('filesystem.stat', DEFAULT_ARC_MAX_FILE)['size']
