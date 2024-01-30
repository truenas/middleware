from auto_config import ip
from middlewared.test.integration.assets.account import user, unprivileged_user_client
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.utils import call, url
from protocols import smb_connection
from pytest_dependency import depends
from time import sleep

import os
import pytest
import requests
import secrets
import string


SMBUSER = 'audit-smb-user'
PASSWD = ''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(10))
pytestmark = pytest.mark.audit


@pytest.fixture(scope='module')
def initialize_for_smb_tests(request):
    with dataset('audit-test-basic', data={'share_type': 'SMB'}) as ds:
        with smb_share(os.path.join('/mnt', ds), 'AUDIT_BASIC_TEST', {
            'purpose': 'NO_PRESET',
            'guestok': False,
            'audit': {'enable': True}
        }) as s:
            with user({
                'username': SMBUSER,
                'full_name': SMBUSER,
                'group_create': True,
                'password': PASSWD,
                'smb': True
            }) as u:
                yield {'dataset': ds, 'share': s, 'user': u}


def test_audit_config_defaults(request):
    config = call('audit.config')
    for key in [
        'retention',
        'quota',
        'reservation',
        'quota_fill_warning',
        'quota_fill_critical',
        'remote_logging_enabled',
        'space'
    ]:
        assert key in config, str(config)

    assert config['retention'] == 7
    assert config['quota'] == 0
    assert config['reservation'] == 0
    assert config['quota_fill_warning'] == 80
    assert config['quota_fill_critical'] == 95
    assert config['remote_logging_enabled'] is False
    for key in ['used', 'used_by_snapshots', 'used_by_dataset', 'used_by_reservation', 'available']:
        assert key in config['space'], str(config['space'])

    assert 'SMB' in config['enabled_services']


def test_audit_config_updates(request):
    """
    This test just validates that setting values has expected results.
    """
    new_config = call('audit.update', {'retention': 10})
    assert new_config['retention'] == 10

    new_config = call('audit.update', {'quota': 1})
    assert new_config['quota'] == 1

    # Check that we're actually setting the quota by evaluating available space
    # we should be within 1 Mib of quota target (sql database will already be written)
    assert abs(new_config['space']['available'] - 1024 ** 3) < 1024 ** 2

    new_config = call('audit.update', {'reservation': 1})
    assert new_config['reservation'] == 1
    assert new_config['space']['used_by_reservation'] != 0

    new_config = call('audit.update', {
        'quota_fill_warning': 70,
        'quota_fill_critical': 80
    })

    assert new_config['quota_fill_warning'] == 70
    assert new_config['quota_fill_critical'] == 80


@pytest.mark.dependency(name="AUDIT_OPS_PERFORMED")
def test_audit_query(initialize_for_smb_tests):
    share = initialize_for_smb_tests['share']
    with smb_connection(
        host=ip,
        share=share['name'],
        username=SMBUSER,
        password=PASSWD,
    ) as c:
        fd = c.create_file('testfile.txt', 'w')
        for i in range(0, 3):
            c.write(fd, b'foo')
            c.read(fd, 0, 3)
        c.close(fd, True)

    sleep(10)
    ops = call('audit.query', {
        'services': ['SMB'],
        'query-filters': [['username', '=', SMBUSER]],
        'query-options': {'count': True}
    })
    assert ops > 0


def test_audit_export(request):
    depends(request, ["AUDIT_OPS_PERFORMED"], scope="session")
    for backend in ['CSV', 'JSON', 'YAML']:
        report_path = call('audit.export', {'export_format': backend}, job=True)
        assert report_path.startswith('/audit/reports/root/')
        st = call('filesystem.stat', report_path)
        assert st['size'] != 0, str(st)

        job_id, path = call("core.download", "audit.download_report", [{
            "report_name": os.path.basename(report_path)
        }], f"report.{backend.lower()}")
        r = requests.get(f"{url()}{path}")
        r.raise_for_status()
        assert len(r.content) == st['size']


def test_audit_export_nonroot(request):
    depends(request, ["AUDIT_OPS_PERFORMED"], scope="session")

    with unprivileged_user_client(roles=['SYSTEM_AUDIT_READ', 'FILESYSTEM_ATTRS_READ']) as c:
        me = c.call('auth.me')
        username = me['pw_name']

        for backend in ['CSV', 'JSON', 'YAML']:
            report_path = c.call('audit.export', {'export_format': backend}, job=True)
            assert report_path.startswith(f'/audit/reports/{username}/')
            st = c.call('filesystem.stat', report_path)
            assert st['size'] != 0, str(st)

            job_id, path = c.call("core.download", "audit.download_report", [{
                "report_name": os.path.basename(report_path)
            }], f"report.{backend.lower()}")
            r = requests.get(f"{url()}{path}")
            r.raise_for_status()
            assert len(r.content) == st['size']
