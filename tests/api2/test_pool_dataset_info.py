import contextlib
import pytest

from middlewared.test.integration.utils import call
from middlewared.test.integration.assets.docker import docker
from middlewared.test.integration.assets.pool import pool, another_pool, dataset


@pytest.fixture(scope='function')
def pool_dataset_zvol_app():
    pool_list = [pool]
    ds_list = []
    zv_list = []
    app_list = []

    # Create dataset and zvol on current pool
    # Make another pool for an app
    with contextlib.ExitStack() as es:
        # Create datasets on existing pool
        ds = es.enter_context(dataset(f"dataset_{pool}"))
        ds_list.append(ds)

        # Create zvol on existing pool
        zv = es.enter_context(dataset(f"zvol_{pool}", {"type": "VOLUME", "volsize": 1048576}))
        zv_list.append(zv)

        # Create another pool
        p = es.enter_context(another_pool())
        pool_list.append(p['name'])

        # Create a docker dataset in the pool
        dc = es.enter_context(docker(p))
        app_list.append(dc['dataset'])

        yield {'pools': pool_list, 'zvols': zv_list, 'datasets': ds_list, 'apps': app_list}


def test_recommended_zvol_blocksize():
    assert call("pool.dataset.recommended_zvol_blocksize", pool) == "16K"


def test_pool_filesystem_choices(pool_dataset_zvol_app):
    """ filesystem_choices returns a list of datasets and pools
        It should not list boot-pool or the system dataset (.system) """

    created_items = pool_dataset_zvol_app
    assert 'apps' in created_items

    # Default is to list both FILESYSTEM and VOLUME
    fc_list_all = call('pool.filesystem_choices')
    should_contain = dict(filter(lambda item: 'apps' not in item[0], created_items.items()))
    expected_list = [item for sl in should_contain.values() for item in sl]
    assert sorted(fc_list_all) == sorted(expected_list)

    # Only one volume created
    fc_vol_list = call('pool.filesystem_choices', ["VOLUME"])
    assert fc_vol_list == created_items['zvols']

    # Make sure we get only filesystem items and only ones we expect
    fc_fs_list = call('pool.filesystem_choices', ["FILESYSTEM"])
    should_contain_fs = dict(filter(lambda item: 'zvols' not in item[0], should_contain.items()))
    expected_fs_list = [item for sl in should_contain_fs.values() for item in sl]
    assert sorted(fc_fs_list) == sorted(expected_fs_list)
