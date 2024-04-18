import sys
from os import getcwd

apifolder = getcwd()
sys.path.append(apifolder)

from auto_config import ha
from middlewared.test.integration.utils import call

# this is found in middlewared.plugins.sysctl.sysctl_info
# but the client running the tests isn't guaranteed to have
# the middlewared application installed locally
DEFAULT_ARC_MAX_FILE = '/var/run/middleware/default_arc_max'


def test_sysctl_arc_max_is_set():
    """Middleware should have created this file and written a number
    to it early in the boot process. That's why we check it here in
    this test so early"""
    assert call('filesystem.stat', DEFAULT_ARC_MAX_FILE)['size']


def test_database_mode():
    """Test the mode of the database file."""
    db_name = "/data/freenas-v1.db"
    db_mode = 0o600
    mode = call('filesystem.stat', db_name)['mode']
    assert mode & 0o777 == db_mode, mode
    if ha:
        call('failover.sync_to_peer')
        mode = call('failover.call_remote', 'filesystem.stat', [db_name])['mode']
        assert mode & 0o777 == db_mode, mode
