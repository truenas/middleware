import pytest

from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call, mock, ssh


POOL_NAME = 'test_pool_import'


def test_does_not_touch_normal_pool():
    """
    Verify that when we import a pool that is already ok, no additional actions are performed.
    """
    with another_pool({'name': POOL_NAME}) as pool:
        # Will fail if we try to call this method
        with mock(
            'pool.dataset.update_impl',
            exception='The imported pool is already ok, this method should not be called',
        ):
            # Export and import the pool
            call('pool.export', pool['id'], job=True)
            call('pool.import_pool', {'guid': pool['guid'], 'name': POOL_NAME}, job=True)


def test_resets_explicit_mountpoint():
    """
    Verify that pool import resets explicitly set mountpoints to use default source.

    Even when the mountpoint value is correct, having it explicitly set (source=local)
    rather than inherited (source=default) causes problems during replication - the
    explicit mountpoint property gets replicated to the target system where the paths
    differ. See NAS-139363.

    This test verifies that on import, TrueNAS resets the mountpoint to inherit from
    the default, ensuring source becomes "default" while preserving the correct value.
    """
    with another_pool({'name': POOL_NAME}) as pool:
        # After pool creation, mountpoint source is "default". Set it explicitly
        # to make source "local". We use the ZFS default mountpoint format (/{pool_name}).
        ssh(f'zfs set mountpoint=/{POOL_NAME} {POOL_NAME}')

        # Verify the source is "local" before export
        assert ssh(f'zfs get -H -o source mountpoint {POOL_NAME}').strip() == 'local'
        assert ssh(f'zfs get -H -o value mountpoint {POOL_NAME}').strip() == f'/mnt/{POOL_NAME}'

        # Export and import the pool
        call('pool.export', pool['id'], job=True)
        call('pool.import_pool', {'guid': pool['guid'], 'name': POOL_NAME}, job=True)

        # Verify the mountpoint value is correct and source changed to "default"
        assert ssh(f'zfs get -H -o source mountpoint {POOL_NAME}').strip() == 'default'
        assert ssh(f'zfs get -H -o value mountpoint {POOL_NAME}').strip() == f'/mnt/{POOL_NAME}'
