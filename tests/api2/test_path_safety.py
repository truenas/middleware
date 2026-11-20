import errno
import shlex

import pytest

from middlewared.service_exception import CallError, ValidationErrors
from middlewared.test.integration.assets.account import unprivileged_user_client, user
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.utils import call, ssh


@pytest.mark.parametrize('name', ['\\056\\056', 'a"b'])
def test_nfs_refuses_paths_exportfs_would_rewrite(name):
    with dataset('nfs_path_chars') as ds:
        path = f'/mnt/{ds}/{name}'
        ssh(f'mkdir {shlex.quote(path)}')
        with pytest.raises(ValidationErrors, match='NFS cannot export a path that contains'):
            call('sharing.nfs.create', {'path': path})


@pytest.mark.parametrize('suffix', ['/', '../..', 'a//b'])
def test_smb_path_suffix_stays_beneath_share(suffix):
    with dataset('smb_path_suffix', {'share_type': 'SMB'}) as ds:
        with smb_share(f'/mnt/{ds}', 'path_suffix_test') as share:
            with pytest.raises(ValidationErrors, match='must be a relative path'):
                call('sharing.smb.update', share['id'], {
                    'purpose': 'LEGACY_SHARE',
                    'options': {'path_suffix': suffix},
                })


def test_ssh_keyscan_host_is_not_an_option():
    token = 'keyscan-probe-token'
    ssh(f'echo {token} > /tmp/keyscan_probe')
    try:
        with pytest.raises(CallError) as ce:
            call('keychaincredential.remote_ssh_host_key_scan', {'host': '-f/tmp/keyscan_probe', 'connect_timeout': 3})
        assert token not in ce.value.errmsg
    finally:
        ssh('rm -f /tmp/keyscan_probe')


def test_zfs_tunable_must_name_a_parameter():
    with pytest.raises(ValidationErrors, match='ZFS module does not accept'):
        call('tunable.create', {
            'type': 'ZFS', 'var': '../../../../etc/hostname', 'value': 'x', 'enabled': False,
        }, job=True)


def test_disk_wipe_refuses_paths():
    ssh("head -c 40M /dev/zero | tr '\\0' A > /tmp/wipe_probe")
    try:
        with pytest.raises(CallError) as ce:
            call('disk.wipe', '../tmp/wipe_probe', 'QUICK', False, job=True)
        assert ce.value.errno == errno.EINVAL
        assert ssh('head -c 1 /tmp/wipe_probe') == 'A'
    finally:
        ssh('rm -f /tmp/wipe_probe')


def test_authorized_keys_symlink_is_not_read():
    with dataset('authkeys_symlink') as ds:
        home = f'/mnt/{ds}/symlinkuser'
        with user({
            'username': 'symlinkuser',
            'full_name': 'symlinkuser',
            'group_create': True,
            'home': home,
            'password': 'test1234',
        }) as u:
            ssh(f'mkdir -p {home}/.ssh && ln -sf /etc/hostname {home}/.ssh/authorized_keys')
            assert call('user.get_instance', u['id'])['sshpubkey'] is None


def test_getacl_refuses_fifo():
    with dataset('getacl_fifo') as ds:
        path = f'/mnt/{ds}/fifo'
        ssh(f'mkfifo {path}')
        with pytest.raises(Exception, match='Not a regular file or directory'):
            call('filesystem.getacl', path)


def test_set_zfs_attributes_needs_full_admin_outside_pools():
    with dataset('zfs_attrs_policy') as ds:
        ssh(f'touch /mnt/{ds}/file')
        with unprivileged_user_client(['SHARING_ADMIN']) as c:
            with pytest.raises(ValidationErrors, match='pool mount point'):
                c.call('filesystem.set_zfs_attributes', {
                    'path': '/data/freenas-v1.db', 'zfs_file_attributes': {'immutable': False},
                }, job=True)

            c.call('filesystem.set_zfs_attributes', {
                'path': f'/mnt/{ds}/file', 'zfs_file_attributes': {'immutable': False},
            }, job=True)
