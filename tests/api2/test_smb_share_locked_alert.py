from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.alert import (
    wait_for_share_locked_alert,
    wait_for_share_locked_alert_cleared,
)


PASSPHRASE = '12345678'


def encryption_props():
    return {
        'encryption_options': {'generate_key': False, 'passphrase': PASSPHRASE},
        'encryption': True,
        'inherit_encryption': False,
    }


def test_share_locked_alert_on_dataset_lock_unlock():
    """Locking the dataset behind an SMB share generates a ShareLocked alert.
    Unlocking the dataset clears the alert."""
    with dataset('encrypted_smb', encryption_props()) as ds:
        with smb_share(f'/mnt/{ds}', 'enc_smb_share') as share:
            share_id = share['id']

            # Verify share is not locked initially
            share = call('sharing.smb.get_instance', share_id)
            assert share['locked'] is False

            # Lock the dataset
            call('pool.dataset.lock', ds, job=True)

            # Share should now report as locked
            share = call('sharing.smb.get_instance', share_id)
            assert share['locked'] is True

            # Locking the dataset should generate a ShareLocked alert
            alert = wait_for_share_locked_alert('SMB', share_id)
            assert alert is not None, 'ShareLocked alert was not created after locking dataset'
            assert alert['level'] == 'WARNING'

            # Unlock the dataset — the stale locked-dataset alert must be cleared
            call('pool.dataset.unlock', ds, {
                'datasets': [{'name': ds, 'passphrase': PASSPHRASE}],
                'recursive': True,
            }, job=True)

            # Verify the share is unlocked
            share = call('sharing.smb.get_instance', share_id)
            assert share['locked'] is False

            assert wait_for_share_locked_alert_cleared('SMB', share_id), \
                'ShareLocked alert was not cleared after unlocking dataset'
