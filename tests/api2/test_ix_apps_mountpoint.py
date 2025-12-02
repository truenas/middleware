import pytest

from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call, ssh


APPS_MOUNTPOINT = '/mnt/.ix-apps'
POOL_NAME = 'test_apps_mountpoint'
IX_APPS_DS = f'{POOL_NAME}/ix-apps'


@pytest.fixture(scope='module')
def another_pool_with_ix_apps_ds():
    with another_pool({'name': POOL_NAME}) as pool:
        ssh(f'zfs create {IX_APPS_DS}')
        yield pool


def test_apps_ds_with_another_apps_pool(another_pool_with_ix_apps_ds):
    """
    This test will create a pool with ix-apps dataset
    and then export this new pool and then import it back again. We will like to ensure that in this
    case the imported pool does not has the mountpoint set to apps mountpoint as that will mess up existing
    apps configured pool (if any).
    """
    call('pool.export', another_pool_with_ix_apps_ds['id'], job=True)
    # We will import the pool again now and ensure that the mountpoint of ix-apps
    # dataset in the pool is not apps mountpoint
    call('pool.import_pool', {'guid': another_pool_with_ix_apps_ds['guid'], 'name': POOL_NAME}, job=True)
    assert ssh(f'zfs get -H -o value mountpoint {IX_APPS_DS}').strip() != APPS_MOUNTPOINT
