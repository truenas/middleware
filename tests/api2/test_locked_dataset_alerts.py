"""
Test that alerts are generated when a dataset used by shares/tasks is locked.

This tests the LockableFSAttachmentDelegate children:
- SMBFSAttachmentDelegate (SMB shares)
- NFSFSAttachmentDelegate (NFS shares)
- ISCSIFSAttachmentDelegate (iSCSI extents)
- RsyncFSAttachmentDelegate (Rsync tasks)

Excluded from testing:
- NVMetNamespaceAttachmentDelegate (requires specific hardware)
- CloudSyncFSAttachmentDelegate (requires external credentials)
- CloudBackupFSAttachmentDelegate (requires external credentials)
- WebshareFSAttachmentDelegate (requires TrueNAS Connect)
"""
import contextlib
import pytest
from time import sleep

from middlewared.service_exception import InstanceNotFound
from middlewared.test.integration.assets.pool import another_pool, dataset
from middlewared.test.integration.assets.keychain import localhost_ssh_credentials
from middlewared.test.integration.assets.account import user
from middlewared.test.integration.utils import call, ssh


PASSPHRASE = 'test1234'
SHARE_LOCKED_ALERT = 'ShareLocked'
TASK_LOCKED_ALERT = 'TaskLocked'


@contextlib.contextmanager
def ensure_service_started(service_name):
    """
    Ensure a service is running for the test.
    If the service is not running, start it and stop it after the test.
    """
    was_running = call('service.started', service_name)

    if not was_running:
        call('service.control', 'START', service_name, job=True)

    try:
        yield
    finally:
        if not was_running:
            # Stop the service if we started it
            call('service.control', 'STOP', service_name, job=True)


def encryption_props():
    return {
        'encryption': True,
        'encryption_options': {
            'generate_key': False,
            'passphrase': PASSPHRASE,
        },
        'inherit_encryption': False,
    }


def get_alerts_by_class(alert_class):
    """Get all alerts of a specific class."""
    return [alert for alert in call('alert.list') if alert['klass'] == alert_class]


def wait_for_alert(alert_class, expected_count, timeout=30):
    """Wait for alerts to appear."""
    for _ in range(timeout):
        alerts = get_alerts_by_class(alert_class)
        if len(alerts) >= expected_count:
            return alerts
        sleep(1)
    return get_alerts_by_class(alert_class)


def clear_alerts(alert_class):
    """Clear all alerts of a specific class."""
    for alert in get_alerts_by_class(alert_class):
        call('alert.oneshot_delete', alert_class, alert['key'])


@contextlib.contextmanager
def smb_share(path, name):
    """Create an SMB share."""
    share = call("sharing.smb.create", {
        "path": path,
        "name": name,
    })
    try:
        yield share
    finally:
        try:
            call("sharing.smb.delete", share["id"])
        except InstanceNotFound:
            pass


@contextlib.contextmanager
def nfs_share(path):
    """Create an NFS share."""
    share = call("sharing.nfs.create", {
        "path": path,
    })
    try:
        yield share
    finally:
        try:
            call("sharing.nfs.delete", share["id"])
        except InstanceNotFound:
            pass


@contextlib.contextmanager
def iscsi_extent(name, disk_path):
    """Create an iSCSI extent using a zvol."""
    extent = call("iscsi.extent.create", {
        "name": name,
        "type": "DISK",
        "disk": disk_path,
    })
    try:
        yield extent
    finally:
        try:
            call("iscsi.extent.delete", extent["id"], False, True)
        except InstanceNotFound:
            pass


@contextlib.contextmanager
def rsync_task(path, user_name, ssh_cred_id):
    """Create an rsync task."""
    task = call("rsynctask.create", {
        "path": path,
        "user": user_name,
        "mode": "SSH",
        "ssh_credentials": ssh_cred_id,
        "remotepath": "/tmp",
        "direction": "PUSH",
        "desc": "Test rsync task for locked alert testing",
    })
    try:
        yield task
    finally:
        try:
            call("rsynctask.delete", task["id"])
        except InstanceNotFound:
            pass


@pytest.fixture(scope="module")
def test_pool():
    """Create a test pool for all locked dataset alert tests."""
    with another_pool() as pool:
        yield pool


def test_smb_share_locked_alert(test_pool):
    """Test that locking a dataset with an SMB share generates an alert."""
    clear_alerts(SHARE_LOCKED_ALERT)

    with ensure_service_started('cifs'):
        with dataset("smb_test", encryption_props(), pool=test_pool["name"]) as ds:
            path = f"/mnt/{ds}"

            with smb_share(path, "test_smb"):
                # Lock the dataset
                call("pool.dataset.lock", ds, job=True)

                # Wait for and verify alert
                alerts = wait_for_alert(SHARE_LOCKED_ALERT, 1)
                assert len(alerts) >= 1, f"Expected at least 1 ShareLocked alert, got {len(alerts)}"

                # Verify alert contains SMB share info
                smb_alerts = [a for a in alerts if 'SMB' in a.get('formatted', '')]
                assert len(smb_alerts) >= 1, f"Expected SMB share alert, got alerts: {alerts}"

    clear_alerts(SHARE_LOCKED_ALERT)


def test_nfs_share_locked_alert(test_pool):
    """Test that locking a dataset with an NFS share generates an alert."""
    clear_alerts(SHARE_LOCKED_ALERT)

    with ensure_service_started('nfs'):
        with dataset("nfs_test", encryption_props(), pool=test_pool["name"]) as ds:
            path = f"/mnt/{ds}"

            with nfs_share(path):
                # Lock the dataset
                call("pool.dataset.lock", ds, job=True)

                # Wait for and verify alert
                alerts = wait_for_alert(SHARE_LOCKED_ALERT, 1)
                assert len(alerts) >= 1, f"Expected at least 1 ShareLocked alert, got {len(alerts)}"

                # Verify alert contains NFS share info
                nfs_alerts = [a for a in alerts if 'NFS' in a.get('formatted', '')]
                assert len(nfs_alerts) >= 1, f"Expected NFS share alert, got alerts: {alerts}"

    clear_alerts(SHARE_LOCKED_ALERT)


def test_iscsi_extent_locked_alert(test_pool):
    """Test that locking a zvol with an iSCSI extent generates an alert."""
    clear_alerts(SHARE_LOCKED_ALERT)

    with ensure_service_started('iscsitarget'):
        zvol_props = {
            **encryption_props(),
            "type": "VOLUME",
            "volsize": 1024 * 1024 * 1024,  # 1GB
        }
        with dataset("iscsi_zvol", zvol_props, pool=test_pool["name"]) as zvol_name:
            disk_path = f"zvol/{zvol_name}"

            with iscsi_extent("test_extent", disk_path):
                # Lock the zvol
                call("pool.dataset.lock", zvol_name, job=True)

                # Wait for and verify alert
                alerts = wait_for_alert(SHARE_LOCKED_ALERT, 1)
                assert len(alerts) >= 1, f"Expected at least 1 ShareLocked alert, got {len(alerts)}"

                # Verify alert contains iSCSI extent info
                iscsi_alerts = [a for a in alerts if 'iSCSI' in a.get('formatted', '')]
                assert len(iscsi_alerts) >= 1, f"Expected iSCSI extent alert, got alerts: {alerts}"

    clear_alerts(SHARE_LOCKED_ALERT)


def test_multiple_shares_locked_alerts(test_pool):
    """Test that locking a dataset with multiple shares generates alerts for all."""
    clear_alerts(SHARE_LOCKED_ALERT)

    with ensure_service_started('cifs'):
        with ensure_service_started('nfs'):
            with dataset("multi_share_test", encryption_props(), pool=test_pool["name"]) as ds:
                path = f"/mnt/{ds}"

                with smb_share(path, "test_multi_smb"):
                    with nfs_share(path):
                        # Lock the dataset
                        call("pool.dataset.lock", ds, job=True)

                        # Wait for and verify alerts
                        alerts = wait_for_alert(SHARE_LOCKED_ALERT, 2)
                        assert len(alerts) >= 2, f"Expected at least 2 ShareLocked alerts, got {len(alerts)}"

                        # Verify we have both SMB and NFS alerts
                        formatted_texts = [a.get('formatted', '') for a in alerts]
                        has_smb = any('SMB' in text for text in formatted_texts)
                        has_nfs = any('NFS' in text for text in formatted_texts)
                        assert has_smb, f"Expected SMB alert in: {formatted_texts}"
                        assert has_nfs, f"Expected NFS alert in: {formatted_texts}"

    clear_alerts(SHARE_LOCKED_ALERT)


def test_alert_removed_on_unlock(test_pool):
    """Test that unlocking a dataset removes the locked alert."""
    clear_alerts(SHARE_LOCKED_ALERT)

    with ensure_service_started('cifs'):
        with dataset("unlock_test", encryption_props(), pool=test_pool["name"]) as ds:
            path = f"/mnt/{ds}"

            with smb_share(path, "test_unlock_smb"):
                # Lock the dataset
                call("pool.dataset.lock", ds, job=True)

                # Verify alert exists
                alerts = wait_for_alert(SHARE_LOCKED_ALERT, 1)
                assert len(alerts) >= 1, "Expected ShareLocked alert after locking"

                # Unlock the dataset
                call("pool.dataset.unlock", ds, {
                    "datasets": [{"name": ds, "passphrase": PASSPHRASE}],
                }, job=True)

                # Wait for alert to be removed
                for _ in range(30):
                    alerts = get_alerts_by_class(SHARE_LOCKED_ALERT)
                    if len(alerts) == 0:
                        break
                    sleep(1)

                assert len(alerts) == 0, f"Expected alerts to be cleared after unlock, got {len(alerts)}"

    clear_alerts(SHARE_LOCKED_ALERT)


@pytest.fixture(scope="module")
def rsync_user(test_pool):
    """Create a user for rsync tasks with a proper home directory."""
    with dataset("rsync_user_home", pool=test_pool["name"]) as home_ds:
        home_path = f"/mnt/{home_ds}"
        with user({
            "username": "rsync_test_user",
            "full_name": "Rsync Test User",
            "group_create": True,
            "password": "test1234",
            "home": home_path,
        }) as u:
            yield u


@pytest.fixture(scope="module")
def ssh_creds(rsync_user):
    """Create SSH credentials for rsync."""
    with localhost_ssh_credentials(username=rsync_user["username"]) as creds:
        yield creds


def test_rsync_task_locked_alert(test_pool, rsync_user, ssh_creds):
    """Test that locking a dataset with an rsync task generates a TaskLocked alert."""
    clear_alerts(TASK_LOCKED_ALERT)

    with dataset("rsync_test", encryption_props(), pool=test_pool["name"]) as ds:
        path = f"/mnt/{ds}"
        # Ensure user has access
        ssh(f"chown -R {rsync_user['username']} {path}")

        with rsync_task(path, rsync_user["username"], ssh_creds["credentials"]["id"]):
            # Lock the dataset
            call("pool.dataset.lock", ds, job=True)

            # Wait for and verify alert
            alerts = wait_for_alert(TASK_LOCKED_ALERT, 1)
            assert len(alerts) >= 1, f"Expected at least 1 TaskLocked alert, got {len(alerts)}"

            # Verify alert contains rsync task info
            rsync_alerts = [a for a in alerts if 'Rsync' in a.get('formatted', '')]
            assert len(rsync_alerts) >= 1, f"Expected Rsync task alert, got alerts: {alerts}"

    clear_alerts(TASK_LOCKED_ALERT)
