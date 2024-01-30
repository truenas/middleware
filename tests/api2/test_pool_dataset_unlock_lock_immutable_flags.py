import pytest

from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, ssh

import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)


PASSPHRASE = '12345678'
pytestmark = pytest.mark.zfs


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
            assert call('filesystem.is_immutable', child_ds_mountpoint) is False, child_ds_mountpoint
            call('pool.dataset.lock', child_ds, job=True)
            assert call('filesystem.is_immutable', child_ds_mountpoint) is True, child_ds_mountpoint

        parent_mountpoint = os.path.join('/mnt', parent_ds)
        assert call('filesystem.is_immutable', parent_mountpoint) is False, parent_mountpoint
        call('pool.dataset.lock', parent_ds, job=True)
        assert call('filesystem.is_immutable', parent_mountpoint) is True, parent_mountpoint


def test_unlock_unsets_immutable_flag():
    with dataset('parent', encryption_props()) as parent_ds:
        parent_mountpoint = os.path.join('/mnt', parent_ds)
        with dataset('parent/child', encryption_props()) as child_ds:
            child_ds_mountpoint = os.path.join('/mnt', child_ds)
            call('pool.dataset.lock', parent_ds, job=True)
            assert call('filesystem.is_immutable', parent_mountpoint) is True, parent_mountpoint

            call('pool.dataset.unlock', parent_ds, {
                'datasets': [{'name': parent_ds, 'passphrase': PASSPHRASE}, {'name': child_ds, 'passphrase': 'random'}],
                'recursive': True,
            }, job=True)
            assert call('filesystem.is_immutable', parent_mountpoint) is False, parent_mountpoint
            assert call('filesystem.is_immutable', child_ds_mountpoint) is True, child_ds_mountpoint
            call('pool.dataset.unlock', child_ds, {
                'datasets': [{'name': child_ds, 'passphrase': PASSPHRASE}],
            }, job=True)
            assert call('filesystem.is_immutable', child_ds_mountpoint) is False, child_ds_mountpoint
