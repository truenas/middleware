import contextlib
import time

from middlewared.service_exception import InstanceNotFound
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call


PASSPHRASE = '12345678'


def encryption_props():
    return {
        'encryption_options': {'generate_key': False, 'passphrase': PASSPHRASE},
        'encryption': True,
        'inherit_encryption': False,
    }


@contextlib.contextmanager
def nfs_share(path):
    share_id = call('sharing.nfs.create', {'path': path})['id']
    try:
        yield share_id
    finally:
        with contextlib.suppress(InstanceNotFound):
            call('sharing.nfs.delete', share_id)


@contextlib.contextmanager
def nfs_service():
    call('service.control', 'START', 'nfs', job=True)
    try:
        yield
    finally:
        call('service.control', 'STOP', 'nfs', job=True)


def find_share_locked_alert(share_id):
    for alert in call('alert.list'):
        if alert['klass'] == 'ShareLocked' and f'NFS_{share_id}' in alert['key']:
            return alert
    return None


def wait_for_alert(share_id, timeout=30):
    for _ in range(timeout):
        if alert := find_share_locked_alert(share_id):
            return alert
        time.sleep(1)
    return None


def wait_for_alert_cleared(share_id, timeout=30):
    for _ in range(timeout):
        if find_share_locked_alert(share_id) is None:
            return True
        time.sleep(1)
    return False


def test_share_locked_alert_on_dataset_lock_unlock():
    """Creating an NFS share on a locked dataset generates a ShareLocked alert.
    Unlocking the dataset clears the alert."""
    with dataset('encrypted_nfs', encryption_props()) as ds:
        with nfs_share(f'/mnt/{ds}') as share_id:
            with nfs_service():
                # Verify share is not locked initially
                share = call('sharing.nfs.get_instance', share_id)
                assert share['locked'] is False

                # Lock the dataset
                call('pool.dataset.lock', ds, job=True)

                # Share should now report as locked
                share = call('sharing.nfs.get_instance', share_id)
                assert share['locked'] is True

                # Locking the dataset should generate a ShareLocked alert
                alert = wait_for_alert(share_id)
                assert alert is not None, 'ShareLocked alert was not created after locking dataset'
                assert alert['level'] == 'WARNING'

                # Unlock the dataset — the attachment delegate should clear the alert
                call('pool.dataset.unlock', ds, {
                    'datasets': [{'name': ds, 'passphrase': PASSPHRASE}],
                    'recursive': True,
                }, job=True)

                # Verify the share is unlocked
                share = call('sharing.nfs.get_instance', share_id)
                assert share['locked'] is False

                assert wait_for_alert_cleared(share_id), \
                    'ShareLocked alert was not cleared after unlocking dataset'
