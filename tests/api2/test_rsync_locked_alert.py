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
def rsync_task(path):
    task_id = call('rsynctask.create', {
        'path': path,
        'user': 'root',
        'mode': 'MODULE',
        'remotehost': '127.0.0.1',
        'remotemodule': 'test',
    })['id']
    try:
        yield task_id
    finally:
        with contextlib.suppress(InstanceNotFound):
            call('rsynctask.delete', task_id)


def find_task_locked_alert(task_id):
    for alert in call('alert.list'):
        if alert['klass'] == 'TaskLocked' and f'Rsync_{task_id}' in alert['key']:
            return alert
    return None


def wait_for_alert(task_id, timeout=30):
    for _ in range(timeout):
        if alert := find_task_locked_alert(task_id):
            return alert
        time.sleep(1)
    return None


def wait_for_alert_cleared(task_id, timeout=30):
    for _ in range(timeout):
        if find_task_locked_alert(task_id) is None:
            return True
        time.sleep(1)
    return False


def test_task_locked_alert_on_dataset_lock_unlock():
    """Running an rsync task on a locked dataset generates a TaskLocked alert.
    Unlocking the dataset clears the alert."""
    with dataset('encrypted_rsync', encryption_props()) as ds:
        with rsync_task(f'/mnt/{ds}') as task_id:
            # Verify task is not locked initially
            task = call('rsynctask.get_instance', task_id)
            assert task['locked'] is False

            # Lock the dataset
            call('pool.dataset.lock', ds, job=True)

            # Task should now report as locked
            task = call('rsynctask.get_instance', task_id)
            assert task['locked'] is True

            # Running the task while locked should generate a TaskLocked alert
            call('rsynctask.run', task_id, job=True)

            alert = wait_for_alert(task_id)
            assert alert is not None, 'TaskLocked alert was not created after running locked task'
            assert alert['level'] == 'WARNING'

            # Unlock the dataset — the attachment delegate should clear the alert
            call('pool.dataset.unlock', ds, {
                'datasets': [{'name': ds, 'passphrase': PASSPHRASE}],
                'recursive': True,
            }, job=True)

            # Verify the task is unlocked
            task = call('rsynctask.get_instance', task_id)
            assert task['locked'] is False

            assert wait_for_alert_cleared(task_id), \
                'TaskLocked alert was not cleared after unlocking dataset'
