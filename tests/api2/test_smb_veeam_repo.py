import os
import time
import pytest

from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.utils import call, mock

SHARE_NAME = 'offset_test'
VEEAM_BLOCKSIZE = 131072


@pytest.fixture(autouse=True)
def veeam_entitled():
    with mock('truenas.entitlements.check', args=['SMB_VEEAM', ], declaration="""
        def mock(self, feature):
            from middlewared.api.current import EntitlementEntry
            from middlewared.utils.entitlements import Reason

            return EntitlementEntry(entitled=True, reason=Reason.ENTITLED, message='')
    """):
        yield


def check_veeam_alert(expected, timeout=10):
    # Alert creation/deletion is handled by background jobs; poll until the expected state is reached.
    alert = None
    deadline = time.monotonic() + timeout
    while True:
        alert = None
        for a in call('alert.list'):
            if a['klass'] == 'SMBVeeamFastClone':
                alert = a
                break

        if bool(alert) is expected:
            if expected:
                assert SHARE_NAME in alert['formatted']
            return

        if time.monotonic() >= deadline:
            break

        time.sleep(1)

    assert bool(alert) is expected, str(alert)
    if expected:
        assert SHARE_NAME in alert['formatted']


def test_record_size_smb_create_verror():
    with dataset('smb1mib', data={'recordsize': '1M'}) as ds:
        with pytest.raises(match='The ZFS dataset recordsize property for a dataset used by a Veeam Repository'):
            with smb_share(os.path.join('/mnt', ds), SHARE_NAME, options={
                'purpose': 'VEEAM_REPOSITORY_SHARE',
                'options': {}
            }):
                pass


def test_record_size_smb_update_verror():
    with dataset('smb1mib', data={'recordsize': '1M'}) as ds:
        # First create as regular share
        with smb_share(os.path.join('/mnt', ds), SHARE_NAME) as share:
            with pytest.raises(match='The ZFS dataset recordsize property for a dataset used by a Veeam Repository'):
                call('sharing.smb.update', share['id'], {
                    'purpose': 'VEEAM_REPOSITORY_SHARE',
                    'options': {}
                })


def test_record_size_veeam_share():
    with dataset('smb128k', data={'recordsize': '128K'}) as ds:
        with smb_share(os.path.join('/mnt', ds), SHARE_NAME, options={
            'purpose': 'VEEAM_REPOSITORY_SHARE',
            'options': {}
        }) as share:
            smb_block_size = call('smb.getparm', 'block size', share['name'])

            assert smb_block_size == VEEAM_BLOCKSIZE


def test_veeam_alert():
    """ Changing recordsize under SMB share should generate alert and fixing should clear it. """
    with dataset('smb128k', data={'recordsize': '128K'}) as ds:
        with smb_share(os.path.join('/mnt', ds), SHARE_NAME, options={
            'purpose': 'VEEAM_REPOSITORY_SHARE',
            'options': {}
        }):
            call('pool.dataset.update', ds, {'recordsize': '1M'})
            call('etc.generate', 'smb')
            check_veeam_alert(True)

            call('pool.dataset.update', ds, {'recordsize': '128K'})
            call('etc.generate', 'smb')
            check_veeam_alert(False)
