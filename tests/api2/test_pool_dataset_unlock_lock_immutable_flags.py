import pytest

from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, ssh

import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)


PASSPHRASE = '12345678'


def is_immutable(path: str) -> bool:
    attrs = call('filesystem.stat', path)['attributes']
    return 'IMMUTABLE' in attrs


def encryption_props():
    return {
        'encryption_options': {'generate_key': False, 'passphrase': PASSPHRASE},
        'encryption': True,
        'inherit_encryption': False
    }


def test_lock_sets_immutable_flag():
    with dataset('parent', encryption_props()) as parent_ds:
        with dataset('parent/child', encryption_props()) as child_ds:
            child_ds_mountpoint = os.path.join('/mnt', child_ds)
            assert is_immutable(child_ds_mountpoint) is False, child_ds_mountpoint
            call('pool.dataset.lock', child_ds, job=True)
            assert is_immutable(child_ds_mountpoint) is True, child_ds_mountpoint

        parent_mountpoint = os.path.join('/mnt', parent_ds)
        assert is_immutable(parent_mountpoint) is False, parent_mountpoint
        call('pool.dataset.lock', parent_ds, job=True)
        assert is_immutable(parent_mountpoint) is True, parent_mountpoint


def test_unlock_unsets_immutable_flag():
    with dataset('parent', encryption_props()) as parent_ds:
        parent_mountpoint = os.path.join('/mnt', parent_ds)
        with dataset('parent/child', encryption_props()) as child_ds:
            child_ds_mountpoint = os.path.join('/mnt', child_ds)
            call('pool.dataset.lock', parent_ds, job=True)
            assert is_immutable(parent_mountpoint) is True, parent_mountpoint

            call('pool.dataset.unlock', parent_ds, {
                'datasets': [{'name': parent_ds, 'passphrase': PASSPHRASE}, {'name': child_ds, 'passphrase': 'random'}],
                'recursive': True,
            }, job=True)
            assert is_immutable(parent_mountpoint) is False, parent_mountpoint
            assert is_immutable(child_ds_mountpoint) is True, child_ds_mountpoint
            call('pool.dataset.unlock', child_ds, {
                'datasets': [{'name': child_ds, 'passphrase': PASSPHRASE}],
            }, job=True)
            assert is_immutable(child_ds_mountpoint) is False, child_ds_mountpoint


def test_lock_with_missing_mountpoint():
    """Lock should succeed even when the mountpoint directory doesn't exist on disk."""
    with dataset('ro_parent') as parent_ds:
        with dataset('ro_parent/enc_child', encryption_props()) as child_ds:
            child_mp = os.path.join('/mnt', child_ds)
            call('pool.dataset.lock', child_ds, {'force_umount': True}, job=True)
            # Remove immutable flag and delete mountpoint directory
            ssh(f'chattr -i {child_mp} && rmdir {child_mp}')
            # Set parent readonly so mountpoint can't be recreated
            ssh(f'zfs set readonly=on {parent_ds}')
            try:
                # Manually load key so dataset is in unlocked-but-unmounted state
                ssh(f'echo -n "{PASSPHRASE}" | zfs load-key {child_ds}')
                # Lock should succeed without FileNotFoundError
                call('pool.dataset.lock', child_ds, {'force_umount': True}, job=True)
                ds = call('pool.dataset.get_instance_quick', child_ds, {'encryption': True})
                assert ds['locked'] is True
                assert ds['key_loaded'] is False
            finally:
                ssh(f'zfs set readonly=off {parent_ds}')


def test_unlock_unloads_key_on_mount_failure():
    """Unlock should unload the key when mount fails, keeping dataset in a clean locked state."""
    with dataset('ro_parent') as parent_ds:
        with dataset('ro_parent/enc_child', encryption_props()) as child_ds:
            child_mp = os.path.join('/mnt', child_ds)
            call('pool.dataset.lock', child_ds, {'force_umount': True}, job=True)
            # Remove immutable flag and delete mountpoint directory
            ssh(f'chattr -i {child_mp} && rmdir {child_mp}')
            # Set parent readonly so mount will fail (can't create mountpoint)
            ssh(f'zfs set readonly=on {parent_ds}')
            try:
                result = call('pool.dataset.unlock', child_ds, {
                    'datasets': [{'name': child_ds, 'passphrase': PASSPHRASE}],
                }, job=True)
                # Mount should have failed
                assert result['unlocked'] == []
                assert child_ds in result['failed']
                assert 'Failed to mount dataset' in result['failed'][child_ds]['error']
                # Key should be unloaded — dataset remains cleanly locked
                ds = call('pool.dataset.get_instance_quick', child_ds, {'encryption': True})
                assert ds['locked'] is True
                assert ds['key_loaded'] is False
            finally:
                ssh(f'zfs set readonly=off {parent_ds}')
