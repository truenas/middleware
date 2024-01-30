import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)

import pytest

from functions import if_key_listed, SSH_TEST
from auto_config import ip, sshKey, user, password
from middlewared.test.integration.utils import call, fail
from middlewared.test.integration.utils.client import client

pytestmark = pytest.mark.base


@pytest.fixture(scope='module')
def ip_to_use():
    ip_to_use = ip
    if (ctrl1_ip := os.environ.get('controller1_ip')) is not None:
        ip_to_use = ctrl1_ip

    return ip_to_use


@pytest.fixture(scope='module')
def ws_client(ip_to_use):
    with client(host_ip=ip_to_use) as c:
        yield c


def test_001_is_system_ready(ws_client):
    # other parts of the CI/CD pipeline should have waited
    # for middlewared to report as system.ready so this is
    # a smoke test to see if that's true. If it's not, then
    # the end-user can know that the entire integration run
    # will be non-deterministic because middleware plugins
    # internally expect that the system is ready before
    # propertly responding to REST/WS requests.
    if not ws_client.call('system.ready'):
        fail(f'System is not ready. Currently: {ws_client.call("system.state")}. Aborting tests.')


def test_002_firstboot_checks(ws_client):
    expected_ds = [
        'boot-pool/.system',
        'boot-pool/.system/cores',
        'boot-pool/.system/samba4',
        'boot-pool/.system/webui',
        'boot-pool/grub'
    ]
    # first make sure our expected datasets actually exist
    datasets = [i['name'] for i in ws_client.call('zfs.dataset.query', [], {'select': ['name']})]
    assert all(ds in datasets for ds in expected_ds)

    # now verify that they are mounted with the expected options
    mounts = {i['mount_source']: i for i in ws_client.call('filesystem.mount_info', [['fs_type', '=', 'zfs']])}
    assert all(mounts[ds]['super_opts'] == ['RW', 'XATTR', 'NOACL', 'CASESENSITIVE'] for ds in expected_ds)

    # Verify we don't have any unexpected services running
    # NOTE: smartd is started with "-q never" which means it should
    # always start in all circumstances (even if there is an invalid (or empty) config)
    ignore = ('smartd',)
    for srv in filter(lambda x: x['service'] not in ignore, ws_client.call('service.query')):
        assert srv['enable'] is False
        assert srv['state'] == 'STOPPED'

    # verify posix mode, uid and gid for standard users
    stat_info = {
        '/home/admin': {'mode': 0o40700, 'uid': 950, 'gid': 950},
        '/root': {'mode': 0o40700, 'uid': 0, 'gid': 0},
    }
    for path, expected_stat in stat_info.items():
        assert all(ws_client.call('filesystem.stat', path)[key] == expected_stat[key] for key in expected_stat)


def test_003_enable_ssh_for_root_user(ws_client):
    # enable ssh password login for root user (used by all tests that come after this one)
    filters, options = [['username', '=', 'root']], {'get': True}
    root_user_db_id = ws_client.call('user.query', filters, options)['id']
    ws_client.call('user.update', root_user_db_id, {'sshpubkey': sshKey, 'ssh_password_enabled': True})
    assert ws_client.call('user.query', filters, options)['ssh_password_enabled'] is True


def test_004_enable_and_start_ssh(ws_client):
    # enable ssh to start at boot
    ws_client.call('service.update', 'ssh', {'enable': True})
    filters, options = [['srv_service', '=', 'ssh']], {'get': True}
    assert ws_client.call('datastore.query', 'services.services', filters, options)['srv_enable'] is True

    # start ssh
    ws_client.call('service.start', 'ssh')
    assert ws_client.call('service.query', [['service', '=', 'ssh']], options)['state'] == 'RUNNING'


def test_005_ssh_using_root_password(ip_to_use):
    results = SSH_TEST('ls -la', user, password, ip_to_use)
    if not results['result']:
        fail(f"SSH is not usable: {results['output']}. Aborting tests.")


def test_006_setup_and_login_using_root_ssh_key(ip_to_use):
    assert os.environ.get('SSH_AUTH_SOCK') is not None
    assert if_key_listed() is True  # horrible function name
    results = SSH_TEST('ls -la', user, None, ip_to_use)
    assert results['result'] is True, results['output']


@pytest.mark.parametrize('account', [
    {'type': 'GROUP', 'gid': 544, 'name': 'builtin_administrators'},
    {'type': 'GROUP', 'gid': 545, 'name': 'builtin_users'},
    {'type': 'GROUP', 'gid': 951, 'name': 'truenas_readonly_administrators'},
    {'type': 'GROUP', 'gid': 952, 'name': 'truenas_sharing_administrators'},
])
def test_007_check_local_accounts(account):
    entry = call('group.query', [['gid', '=', account['gid']]])
    if not entry:
        fail(f'{account["gid"]}: entry does not exist in db')

    entry = entry[0]
    if entry['group'] != account['name']:
        fail(f'Group has unexpected name: {account["name"]} -> {entry["group"]}')
