from middlewared.service_exception import ValidationError, CallError
from middlewared.test.integration.assets.account import user, unprivileged_user_client
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.utils import busy_wait_on_job, call, url
from middlewared.test.integration.utils.audit import get_audit_entry

from auto_config import ha
from protocols import smb_connection
from time import sleep

import os
import pytest
import requests
import secrets
import string


SMBUSER = 'audit-smb-user'
PASSWD = ''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(10))
AUDIT_DATASET_CONFIG = {
    # keyname : "audit"=audit only setting, "zfs"=zfs dataset setting, "ro"=read-only (not a setting)
    'retention': 'audit',
    'quota': 'zfs',
    'reservation': 'zfs',
    'quota_fill_warning': 'zfs',
    'quota_fill_critical': 'zfs',
    'remote_logging_enabled': 'other',
    'space': 'ro'
}
MiB = 1024**2
GiB = 1024**3


# =====================================================================
#                     Fixtures and utilities
# =====================================================================
class AUDIT_CONFIG():
    defaults = {
        'retention': 7,
        'quota': 0,
        'reservation': 0,
        'quota_fill_warning': 75,
        'quota_fill_critical': 95
    }


def get_zfs(data_type, key, zfs_config):
    """ Get the equivalent ZFS value associated with the audit config setting """

    types = {
        'zfs': {
            'reservation': zfs_config['properties']['refreservation']['value'] or 0,
            'quota': zfs_config['properties']['refquota']['value'] or 0,  # audit quota == ZFS refquota
            'refquota': zfs_config['properties']['refquota']['value'] or 0,
            'quota_fill_warning': zfs_config['org.freenas:quota_warning'],
            'quota_fill_critical': zfs_config['org.freenas:quota_critical']
        },
        'space': {
            'used': zfs_config['properties']['used']['value'],
            'used_by_snapshots': zfs_config['properties']['usedbysnapshots']['value'],
            'available': zfs_config['properties']['available']['value'],
            'used_by_dataset': zfs_config['properties']['usedbydataset']['value'],
            # We set 'refreservation' and there is no 'usedbyreservation'
            'used_by_reservation': zfs_config['properties']['usedbyrefreservation']['value']
        }
    }
    return types[data_type][key]


def check_audit_download(report_path, report_type, tag=None):
    """ Download audit DB (root user)
    If requested, assert the tag is present
    INPUT: report_type ['CSV'|'JSON'|'YAML']
    RETURN: lenght of content (bytes)
    """
    job_id, url_path = call(
        "core.download", "audit.download_report",
        [{"report_name": os.path.basename(report_path)}],
        f"report.{report_type.lower()}"
    )
    r = requests.get(f"{url()}{url_path}")
    r.raise_for_status()
    if tag is not None:
        assert f"{tag}" in r.text
    return len(r.content)


@pytest.fixture(scope='class')
def initialize_for_smb_tests():
    with dataset('audit-test-basic', data={'share_type': 'SMB'}) as ds:
        with smb_share(os.path.join('/mnt', ds), 'AUDIT_BASIC_TEST', {
            'purpose': 'LEGACY_SHARE',
            'options': {'guestok': False},
            'audit': {'enable': True, 'ignore_list': ['root']}
        }) as s:
            with user({
                'username': SMBUSER,
                'full_name': SMBUSER,
                'group_create': True,
                'password': PASSWD,
                'smb': True
            }) as u:
                yield {'dataset': ds, 'share': s, 'user': u}


@pytest.fixture(scope='class')
def init_audit():
    """ Provides the audit and dataset configs and cleans up afterward """
    try:
        dataset = call('audit.get_audit_dataset')
        config = call('audit.config')
        yield (config, dataset)
    finally:
        call('audit.update', AUDIT_CONFIG.defaults)


@pytest.fixture(scope='class')
def standby_audit_event():
    """ HA system: Create an audit event on the standby node
    Attempt to delete a built-in user on the standby node
    """
    event = "user.delete"
    username = "backup"
    user = call('user.query', [["username", "=", username]], {"select": ["id"], "get": True})

    # Generate an audit entry on the remote node
    with pytest.raises(CallError):
        call('failover.call_remote', event, [user['id']])

    yield {
        "event": event,
        "username": username,
        "user_id": user["id"]
    }


# =====================================================================
#                           Tests
# =====================================================================
class TestAuditConfig:
    def test_audit_config_defaults(self, init_audit):
        (config, dataset) = init_audit

        # Confirm existence of config entries
        for key in [k for k in AUDIT_DATASET_CONFIG]:
            assert key in config, str(config)

        # Confirm audit default config settings
        assert config['retention'] == AUDIT_CONFIG.defaults['retention']
        assert config['quota'] == AUDIT_CONFIG.defaults['quota']
        assert config['reservation'] == AUDIT_CONFIG.defaults['reservation']
        assert config['quota_fill_warning'] == AUDIT_CONFIG.defaults['quota_fill_warning']
        assert config['quota_fill_critical'] == AUDIT_CONFIG.defaults['quota_fill_critical']
        assert config['remote_logging_enabled'] is False
        for key in ['used', 'used_by_snapshots', 'used_by_dataset', 'used_by_reservation', 'available']:
            assert key in config['space'], str(config['space'])

        for service in ['MIDDLEWARE', 'SMB', 'SUDO']:
            assert service in config['enabled_services']

        # Confirm audit dataset settings
        for key in [k for k in AUDIT_DATASET_CONFIG if AUDIT_DATASET_CONFIG[k] == 'zfs']:
            assert get_zfs('zfs', key, dataset) == config[key], f"config[{key}] = {config[key]}"

    def test_audit_config_dataset_defaults(self, init_audit):
        """ Confirm Audit dataset uses Audit default settings """
        (unused, ds_config) = init_audit
        assert ds_config['org.freenas:refquota_warning'] == AUDIT_CONFIG.defaults['quota_fill_warning']
        assert ds_config['org.freenas:refquota_critical'] == AUDIT_CONFIG.defaults['quota_fill_critical']

    def test_audit_config_updates(self):
        """
        This test validates that setting values has expected results.
        """
        new_config = call('audit.update', {'retention': 10})
        assert new_config['retention'] == 10

        # quota are in units of GiB
        new_config = call('audit.update', {'quota': 1})
        assert new_config['quota'] == 1
        audit_dataset = call('audit.get_audit_dataset')

        # ZFS value is in units of bytes.  Convert to GiB for comparison.
        assert get_zfs('zfs', 'refquota', audit_dataset) // GiB == new_config['quota']

        # Confirm ZFS and audit config are in sync
        assert new_config['space']['available'] == get_zfs('space', 'available', audit_dataset)
        assert new_config['space']['used_by_dataset'] == get_zfs('space', 'used', audit_dataset)

        # Check that we're actually setting the quota by evaluating available space
        # Change the the quota to something more interesting
        new_config = call('audit.update', {'quota': 2})
        assert new_config['quota'] == 2

        audit_dataset = call('audit.get_audit_dataset')
        assert get_zfs('zfs', 'refquota', audit_dataset) == 2*GiB  # noqa (allow 2*GiB)

        used_in_dataset = get_zfs('space', 'used_by_dataset', audit_dataset)
        assert 2*GiB - new_config['space']['available'] == used_in_dataset  # noqa (allow 2*GiB)

        new_config = call('audit.update', {'reservation': 1})
        assert new_config['reservation'] == 1
        assert new_config['space']['used_by_reservation'] != 0

        new_config = call('audit.update', {
            'quota_fill_warning': 70,
            'quota_fill_critical': 80
        })

        assert new_config['quota_fill_warning'] == 70
        assert new_config['quota_fill_critical'] == 80

        # Test disable reservation
        new_config = call('audit.update', {'reservation': 0})
        assert new_config['reservation'] == 0

        # Test disable quota
        new_config = call('audit.update', {'quota': 0})
        assert new_config['quota'] == 0

    @pytest.mark.skipif(not ha, reason="Skip HA tests")
    def test_audit_config_remote_node(self, init_audit):
        """ Confirm audit dataset changes are mirrored to the remote node"""
        (unused, ds_config) = init_audit
        # New temporary setting that's different from current
        new_setting = ds_config['org.freenas:refquota_warning'] + 5

        call('audit.update', {'quota_fill_warning': new_setting})
        remote = call('failover.call_remote', 'audit.get_audit_dataset')
        assert remote['org.freenas:refquota_warning'] == new_setting


class TestAuditOps:
    def test_audit_query(self, initialize_for_smb_tests):
        # If this test has been run more than once on this VM, then
        # the audit DB _will_ record the creation.
        # Let's get the starting count.
        initial_ops_count = call('audit.query', {
            'services': ['SMB'],
            'query-filters': [['username', '=', SMBUSER]],
            'query-options': {'count': True}
        })

        share = initialize_for_smb_tests['share']
        with smb_connection(
            share=share['name'],
            username=SMBUSER,
            password=PASSWD,
        ) as c:
            fd = c.create_file('testfile.txt', 'w')
            for i in range(0, 3):
                c.write(fd, b'foo')
                c.read(fd, 0, 3)
            c.close(fd, True)

        retries = 2
        ops_count = initial_ops_count
        while retries > 0 and (ops_count - initial_ops_count) <= 0:
            sleep(5)
            ops_count = call('audit.query', {
                'services': ['SMB'],
                'query-filters': [['username', '=', SMBUSER]],
                'query-options': {'count': True}
            })
            retries -= 1
        assert ops_count > initial_ops_count, f"retries remaining = {retries}"

    def test_audit_order_by(self):
        entries_forward = call('audit.query', {'services': ['SMB'], 'query-options': {
            'order_by': ['audit_id'],
            'limit': 1000,
        }})

        entries_reverse = call('audit.query', {'services': ['SMB'], 'query-options': {
            'order_by': ['-audit_id'],
            'limit': 1000,
        }})

        head_forward_id = entries_forward[0]['audit_id']
        tail_forward_id = entries_forward[-1]['audit_id']

        head_reverse_id = entries_reverse[0]['audit_id']
        tail_reverse_id = entries_reverse[-1]['audit_id']

        assert head_forward_id == tail_reverse_id
        assert tail_forward_id == head_reverse_id

    def test_audit_export(self):
        for backend in ['CSV', 'JSON', 'YAML']:
            report_path = call('audit.export', {'export_format': backend}, job=True)
            assert report_path.startswith('/audit/reports/root/')
            st = call('filesystem.stat', report_path)
            assert st['size'] != 0, str(st)

            content_len = check_audit_download(report_path, backend)
            assert content_len == st['size']

    def test_audit_export_nonroot(self):
        with unprivileged_user_client(roles=['SYSTEM_AUDIT_READ', 'FILESYSTEM_ATTRS_READ']) as c:
            me = c.call('auth.me')
            username = me['pw_name']

            for backend in ['CSV', 'JSON', 'YAML']:
                report_path = c.call('audit.export', {'export_format': backend}, job=True)
                assert report_path.startswith(f'/audit/reports/{username}/')
                st = c.call('filesystem.stat', report_path)
                assert st['size'] != 0, str(st)

                # Make the call as the client
                job_id, path = c.call(
                    "core.download", "audit.download_report",
                    [{"report_name": os.path.basename(report_path)}],
                    f"report.{backend.lower()}"
                )
                r = requests.get(f"{url()}{path}")
                r.raise_for_status()
                assert len(r.content) == st['size']

    @pytest.mark.parametrize('svc', ["MIDDLEWARE", "SMB"])
    def test_audit_timestamps(self, svc):
        """
        NAS-130373
        Confirm the timestamps are processed as expected
        """
        audit_entry = get_audit_entry(svc)

        ae_ts_ts = int(audit_entry['timestamp'].timestamp())
        ae_msg_ts = int(audit_entry['message_timestamp'])
        assert abs(ae_ts_ts - ae_msg_ts) < 2, f"$date='{ae_ts_ts}, message_timestamp={ae_msg_ts}"


@pytest.mark.skipif(not ha, reason="Skip HA tests")
class TestAuditOpsHA:
    @pytest.mark.parametrize('remote_available', [True, False])
    def test_audit_ha_query(self, standby_audit_event, remote_available):
        '''
        Confirm:
            1) Ability to get a remote node audit event from a healthy remote node
            2) Generate an exception on remote node audit event get if the remote node is unavailable.
        NOTE: The standby_audit_event fixture generates the remote node audit event.
        '''
        event = standby_audit_event['event']
        username = standby_audit_event['username']
        user_id = standby_audit_event['user_id']

        audit_payload = {
            "query-filters": [["event_data.method", "=", event], ["event_data.params", "=", [user_id]]],
            "query-options": {"select": ["event_data", "success"], "limit": 1000},
            "remote_controller": True
        }

        if not remote_available:
            job_id = call('failover.reboot.other_node')
            # Let the reboot get churning
            sleep(2)
            with pytest.raises(ValidationError) as e:
                call('audit.query', audit_payload)
            assert "failed to communicate" in str(e.value)

            # Wait for the remote to return.  This can take a long time
            busy_wait_on_job(job_id)
        else:
            # Handle delays in the audit database
            remote_audit_entry = []
            tries = 5
            while tries > 0 and remote_audit_entry == []:
                sleep(1)
                remote_audit_entry = call('audit.query', audit_payload)
                tries -= 1

            assert tries > 0, f"Failed to get expected audit entry. tries={tries}"
            description = remote_audit_entry[0]['event_data']['description']
            evt0 = remote_audit_entry[0]['event_data']
            assert username in description, f"tries={tries}\nENTRY:\n{evt0}"

    def test_audit_ha_export(self, standby_audit_event):
        """
        Confirm we can download 'Active' and 'Standby' audit DB.
        With a failed user delete on the 'Standby' controller download the
        audit DB from both controllers and confirm the failure is
        in the 'Standby' audit DB and not in the 'Active' audit DB.
        """
        assert standby_audit_event
        username = standby_audit_event['username']
        report_path_active = call('audit.export', {'export_format': 'CSV'}, job=True)
        report_path_standby = call('audit.export', {'export_format': 'CSV', 'remote_controller': True}, job=True)

        # Confirm entry NOT in active controller audit DB
        with pytest.raises(AssertionError):
            check_audit_download(report_path_active, 'CSV', f"Delete user {username}")

        # Confirm entry IS in standby controller audit DB
        check_audit_download(report_path_standby, 'CSV', f"Delete user {username}")
