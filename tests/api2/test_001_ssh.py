import collections
import json
import os

import pytest

from functions import if_key_listed, SSH_TEST
from auto_config import sshKey, user, password
from middlewared.test.integration.utils import fail, ssh
from middlewared.test.integration.utils.client import client, truenas_server


@pytest.fixture(scope='module')
def ws_client():
    with client(host_ip=truenas_server.ip) as c:
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
        'boot-pool/.system/nfs',
        'boot-pool/.system/samba4',
        'boot-pool/grub'
    ]
    # first make sure our expected datasets actually exist
    datasets = [i['name'] for i in ws_client.call('zfs.resource.query', {'paths': expected_ds, 'properties': None})]
    assert all(ds in datasets for ds in expected_ds)

    # now verify that they are mounted with the expected options
    mounts = {i['mount_source']: i for i in ws_client.call('filesystem.mount_info', [['fs_type', '=', 'zfs']])}
    assert all(mounts[ds]['super_opts'] == ['RW', 'XATTR', 'NOACL', 'CASESENSITIVE'] for ds in expected_ds)

    # Verify we don't have any unexpected services running
    for srv in ws_client.call('service.query'):
        assert srv['enable'] is False, f"{srv['service']} service is unexpectedly enabled"
        assert srv['state'] == 'STOPPED', f"{srv['service']} service expected STOPPED, but found {srv['state']}"

    # verify posix mode, uid and gid for standard users
    stat_info = {
        '/home/truenas_admin': {'mode': 0o40700, 'uid': 950, 'gid': 950},
        '/root': {'mode': 0o40700, 'uid': 0, 'gid': 0},
    }
    for path, expected_stat in stat_info.items():
        actual_stat = ws_client.call('filesystem.stat', path)
        assert all(actual_stat[key] == expected_stat[key] for key in expected_stat), \
            f"Expected {expected_stat} but found {actual_stat}"


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
    ws_client.call('service.control', 'START', 'ssh', job=True)
    assert ws_client.call('service.query', [['service', '=', 'ssh']], options)['state'] == 'RUNNING'


def test_005_ssh_using_root_password():
    results = SSH_TEST('ls -la', user, password)
    if not results['result']:
        fail(f"SSH is not usable: {results['output']}. Aborting tests.")


def test_006_setup_and_login_using_root_ssh_key():
    assert os.environ.get('SSH_AUTH_SOCK') is not None
    assert if_key_listed() is True  # horrible function name
    results = SSH_TEST('ls -la', user, None)
    assert results['result'] is True, results['output']


@pytest.mark.parametrize('account', [
    {'type': 'GROUP', 'gid': 544, 'name': 'builtin_administrators'},
    {'type': 'GROUP', 'gid': 545, 'name': 'builtin_users'},
    {'type': 'GROUP', 'gid': 951, 'name': 'truenas_readonly_administrators'},
    {'type': 'GROUP', 'gid': 952, 'name': 'truenas_sharing_administrators'},
])
def test_007_check_local_accounts(ws_client, account):
    entry = ws_client.call('group.query', [['gid', '=', account['gid']]])
    if not entry:
        fail(f'{account["gid"]}: entry does not exist in db')

    entry = entry[0]
    if entry['group'] != account['name']:
        fail(f'Group has unexpected name: {account["name"]} -> {entry["group"]}')


def test_008_check_root_dataset_settings(ws_client):
    data = SSH_TEST('cat /conf/truenas_root_ds.json', user, password)
    if not data['result']:
        fail(f'Unable to get dataset schema: {data["output"]}')

    try:
        ds_schema = json.loads(data['stdout'])
    except Exception as e:
        fail(f'Unable to load dataset schema: {e}')

    data = SSH_TEST('zfs get -o value -H truenas:developer /', user, password)
    if not data['result']:
        fail('Failed to determine whether developer mode enabled')

    is_dev = data['stdout'] == 'on'

    for entry in ds_schema:
        fhs_entry = entry['fhs_entry']
        mp = fhs_entry.get('mountpoint') or os.path.join('/', fhs_entry['name'])
        if (force_mode := fhs_entry.get('mode')):
            st = ws_client.call('filesystem.stat', mp)
            assert st['mode'] & 0o777 == force_mode, f'{entry["ds"]}: unexpected permissions on dataset'

        fs = ws_client.call('filesystem.mount_info', [['mountpoint', '=', mp]])
        if not fs:
            fail(f'{mp}: mountpoint not found')

        fs = fs[0]

        if fs['mount_source'] != entry['ds']:
            fail(f'{fs["mount_source"]}: unexpected filesystem, expected {entry["ds"]}')

        if is_dev:
            # This is a run where root filesystem is unlocked. Don't obther checking remaining
            continue

        for opt in fhs_entry['options']:
            # setuid=off translates to nosuid in mountpoint opts
            # NOSUID also means NODEV which is why NOSETUID was added
            if opt == 'NOSETUID':
                opt = 'NOSUID'
            # DEV is used to change inherited datasets where parent is using NODEV option
            # which means we need to make sure NODEV is not in the mount options
            if opt == 'DEV':
                if 'NODEV' in fs['mount_opts'] or 'NODEV' in fs['super_opts']:
                    assert 'NODEV' not in fs['mount_opts'] and 'NODEV' not in fs['super_opts'], f"NODEV: present in mount opts for {mp}: {fs['mount_opts']} - {fs['super_opts']}"
            elif opt not in fs['mount_opts'] and opt not in fs['super_opts']:
                assert opt in fs['mount_opts'], f'{opt}: mount option not present for {mp}: {fs["mount_opts"]}'


def test_009_check_listening_ports():
    listen = collections.defaultdict(set)
    for line in ssh("netstat -tuvpan | grep LISTEN").splitlines():
        proto, _, _, local, _, _, process = line.split(maxsplit=6)
        if proto == "tcp":
            host, port = local.split(":", 1)
            if host != "0.0.0.0":
                continue
        elif proto == "tcp6":
            host, port = local.rsplit(":", 1)
            if host != "::":
                continue
        else:
            assert False, f"Unknown protocol {proto}"

        port = int(port)
        if port in [22, 80, 111, 443]:
            continue

        listen[int(port)].add(process.strip())

    assert not listen, f"Invalid ports listening on 0.0.0.0: {dict(listen)}"
