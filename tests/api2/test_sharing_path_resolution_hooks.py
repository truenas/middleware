"""
Test dataset/relative_path resolution hooks for sharing services.

This test verifies that the dataset/relative_path fields stored for a share follow the dataset that holds its path:
they resolve while that dataset is locked, are corrected when an encrypted dataset is unlocked, and move to a dataset
mounted over the path later.
"""
import time

import pytest

from middlewared.test.integration.assets.entitlements import entitled
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, client, ssh


PASSPHRASE = 'test_passphrase_12345'


def changed_to(events, share_id, dataset):
    """Wait for a change event that resolves the share to `dataset`."""
    for _ in range(10):
        if any(
            event_type == 'CHANGED' and message['id'] == share_id and message['fields']['dataset'] == dataset
            for event_type, message in events
        ):
            return True
        time.sleep(1)
    return False


@pytest.fixture
def encrypted_dataset():
    """Create an encrypted dataset that will be locked/unlocked during tests."""
    with dataset('encrypted_share_test', {
        'encryption': True,
        'inherit_encryption': False,
        'encryption_options': {'passphrase': PASSPHRASE}
    }) as ds:
        # Create a subdirectory for the share
        share_path = f'/mnt/{ds}/share_dir'
        ssh(f'mkdir -p {share_path}')
        yield {
            'name': ds,
            'path': share_path,
            'passphrase': PASSPHRASE,
        }


def test_smb_share_path_resolution_after_unlock(encrypted_dataset):
    """
    Test that SMB share dataset/relative_path are resolved after unlocking.

    This test simulates what happens when migration 0018_resolve_dataset_paths.py
    runs while a dataset is locked - the migration leaves dataset/relative_path as NULL,
    and the hook system should resolve them when the dataset is later unlocked.

    1. Create SMB share with unlocked dataset
    2. Verify dataset and relative_path are set correctly
    3. Lock the dataset
    4. Manually set dataset and relative_path to NULL (simulating migration 0018 running on locked dataset)
    5. Unlock the dataset
    6. Verify hook automatically resolves dataset and relative_path
    """
    ds_name = encrypted_dataset['name']
    share_path = encrypted_dataset['path']

    # Create SMB share while dataset is unlocked
    share = call('sharing.smb.create', {
        'name': 'test_locked_smb',
        'path': share_path,
        'purpose': 'DEFAULT_SHARE',
    })

    try:
        # Verify dataset and relative_path were set correctly on creation
        assert share['dataset'] == ds_name
        assert share['relative_path'] == 'share_dir'

        # Lock the dataset
        call('pool.dataset.lock', ds_name, job=True)

        # Verify dataset is locked
        ds = call('pool.dataset.get_instance', ds_name)
        assert ds['locked'] is True

        # Manually set dataset and relative_path to NULL, simulating what happens
        # when migration 0018 runs and encounters a locked dataset
        call('datastore.update', 'sharing.cifs.share', share['id'], {
            'cifs_dataset': None,
            'cifs_relative_path': None,
        })

        # Verify fields are now NULL
        share = call('sharing.smb.get_instance', share['id'])
        assert share['dataset'] is None
        assert share['relative_path'] is None

        with client() as c:
            events = []
            c.subscribe(
                'sharing.smb.query', lambda event_type, **message: events.append((event_type, message)), sync=True
            )

            # Unlock the dataset - this should trigger the dataset.post_unlock hook
            call('pool.dataset.unlock', ds_name, {
                'recursive': True,
                'datasets': [{
                    'name': ds_name,
                    'passphrase': encrypted_dataset['passphrase'],
                }]
            }, job=True)

            assert changed_to(events, share['id'], ds_name)

        # Verify dataset is unlocked
        ds = call('pool.dataset.get_instance', ds_name)
        assert ds['locked'] is False

        # Query the share again to check if hook resolved the path
        share = call('sharing.smb.get_instance', share['id'])

        # Verify dataset and relative_path were resolved by the hook
        assert share['dataset'] == ds_name
        assert share['relative_path'] == 'share_dir'

    finally:
        call('sharing.smb.delete', share['id'])


def test_nfs_share_path_resolution_after_unlock(encrypted_dataset):
    """
    Test that NFS share dataset/relative_path are corrected after unlocking.

    This test simulates a share resolved to the dataset above the one holding its path, as a share resolved while
    that dataset was unmounted used to be, and checks the hook system corrects it when the dataset is unlocked.

    1. Create NFS share with unlocked dataset
    2. Verify dataset and relative_path are set correctly
    3. Lock the dataset
    4. Manually set dataset and relative_path to the parent dataset's
    5. Unlock the dataset
    6. Verify hook automatically resolves dataset and relative_path
    """
    ds_name = encrypted_dataset['name']
    share_path = encrypted_dataset['path']

    # Create NFS share while dataset is unlocked
    share = call('sharing.nfs.create', {
        'path': share_path,
    })

    try:
        # Verify dataset and relative_path were set correctly on creation
        assert share['dataset'] == ds_name
        assert share['relative_path'] == 'share_dir'

        # Lock the dataset
        call('pool.dataset.lock', ds_name, job=True)

        # Verify dataset is locked
        ds = call('pool.dataset.get_instance', ds_name)
        assert ds['locked'] is True

        parent, leaf = ds_name.rsplit('/', 1)
        call('datastore.update', 'sharing.nfs.share', share['id'], {
            'nfs_dataset': parent,
            'nfs_relative_path': f'{leaf}/share_dir',
        })

        share = call('sharing.nfs.get_instance', share['id'])
        assert share['dataset'] == parent

        # Unlock the dataset - this should trigger the dataset.post_unlock hook
        call('pool.dataset.unlock', ds_name, {
            'recursive': True,
            'datasets': [{
                'name': ds_name,
                'passphrase': encrypted_dataset['passphrase'],
            }]
        }, job=True)

        # Verify dataset is unlocked
        ds = call('pool.dataset.get_instance', ds_name)
        assert ds['locked'] is False

        # Query the share again to check if hook resolved the path
        share = call('sharing.nfs.get_instance', share['id'])

        # Verify dataset and relative_path were resolved by the hook
        assert share['dataset'] == ds_name
        assert share['relative_path'] == 'share_dir'

    finally:
        call('sharing.nfs.delete', share['id'])


@pytest.fixture
def webshare_entitled():
    # sharing.webshare.create is gated by the WEBSHARE entitlement, which an unlicensed
    # test runner does not have.
    with entitled("WEBSHARE"):
        yield


def test_webshare_path_resolution_while_locked(webshare_entitled, encrypted_dataset):
    """
    Test that a Webshare created while its dataset is locked resolves to that dataset.
    """
    ds_name = encrypted_dataset['name']
    share_path = encrypted_dataset['path']

    call('pool.dataset.lock', ds_name, job=True)

    ds = call('pool.dataset.get_instance', ds_name)
    assert ds['locked'] is True

    share = call('sharing.webshare.create', {
        'name': 'test_locked_webshare',
        'path': share_path,
    })

    try:
        assert share['dataset'] == ds_name
        assert share['relative_path'] == 'share_dir'
        assert share['locked'] is True

        call('pool.dataset.unlock', ds_name, {
            'recursive': True,
            'datasets': [{
                'name': ds_name,
                'passphrase': encrypted_dataset['passphrase'],
            }]
        }, job=True)

        ds = call('pool.dataset.get_instance', ds_name)
        assert ds['locked'] is False

        share = call('sharing.webshare.get_instance', share['id'])

        assert share['dataset'] == ds_name
        assert share['relative_path'] == 'share_dir'

    finally:
        call('sharing.webshare.delete', share['id'])


def test_share_path_resolution_follows_mount():
    """
    Test that a share on an immutable directory resolves, and moves to a dataset later mounted over its path with a
    change event.
    """
    with dataset('path_resolution_mount') as ds:
        share_path = f'/mnt/{ds}/share_dir'
        ssh(f'mkdir {share_path} && chattr +i {share_path}')
        share = call('sharing.nfs.create', {'path': share_path})
        try:
            assert share['dataset'] == ds
            assert share['relative_path'] == 'share_dir'
            # A dataset cannot be created over an existing directory
            ssh(f'chattr -i {share_path} && rmdir {share_path}')

            with client() as c:
                events = []
                c.subscribe(
                    'sharing.nfs.query', lambda event_type, **message: events.append((event_type, message)), sync=True
                )
                with dataset('path_resolution_mount/share_dir') as child:
                    assert changed_to(events, share['id'], child)
                    share = call('sharing.nfs.get_instance', share['id'])
                    assert share['dataset'] == child
                    assert share['relative_path'] == ''
                    call('sharing.nfs.delete', share['id'])
        finally:
            ssh(f'chattr -i {share_path}', check=False)
            if call('sharing.nfs.query', [['id', '=', share['id']]]):
                call('sharing.nfs.delete', share['id'])
