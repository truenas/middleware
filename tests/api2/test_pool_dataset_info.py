import contextlib
import pytest

from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.assets.docker import docker
from middlewared.test.integration.assets.pool import pool, another_pool, dataset, snapshot


@pytest.fixture(scope='function')
def pool_dataset_zvol_snapshot_app():
    """ Create a pool, dataset, zvol, snapshot and an app dataset """

    # The prior tests might have left test cruft.  Be resilient.   We -know- we have a pool.
    pool_list = [line for line in ssh("zpool list -H -o name | grep -v boot-pool").split()]

    try:
        ds_list = [line for line in ssh(f"zfs list -H -t fs -o name | grep -Ev 'boot-pool|{pool}/.system'").split()]
    except AssertionError:
        ds_list = []

    try:
        zv_list = [line for line in ssh("zfs list -H -t vol -o name").split()]
    except AssertionError:
        zv_list = []

    try:
        snap_list = [line for line in ssh(f"zfs list -H -t snap -o name | grep -Ev 'boot-pool|{pool}/.system'").split()]
    except AssertionError:
        snap_list = []

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

        # Create a snapshot
        s = es.enter_context(snapshot(pool, "snap_deleteme"))
        snap_list.append(s)

        yield {'pools': pool_list, 'zvols': zv_list, 'datasets': ds_list, 'snaps': snap_list, 'apps': app_list}


def test_recommended_zvol_blocksize():
    assert call("pool.dataset.recommended_zvol_blocksize", pool) == "16K"


def test_pool_filesystem_choices(pool_dataset_zvol_snapshot_app):
    """ filesystem_choices returns a list of datasets and pools
        It should not list boot-pool or the system dataset (.system) """

    created_items = pool_dataset_zvol_snapshot_app
    assert 'apps' in created_items

    # Default is to list both FILESYSTEM and VOLUME
    fc_set_all = set(call('pool.filesystem_choices'))
    should_contain = dict(filter(lambda item: item[0] not in ['apps', 'snaps'], created_items.items()))
    expected_set = set([item for sl in should_contain.values() for item in sl])
    assert sorted(fc_set_all) == sorted(expected_set)

    # Test request for volumes
    fc_vol_list = call('pool.filesystem_choices', ["VOLUME"])
    assert sorted(fc_vol_list) == sorted(created_items['zvols'])

    # Make sure we get only filesystem items and only ones we expect
    fc_fs_set = set(call('pool.filesystem_choices', ["FILESYSTEM"]))
    should_contain_fs = dict(filter(lambda item: 'zvols' not in item[0], should_contain.items()))
    expected_fs_set = set([item for sl in should_contain_fs.values() for item in sl])
    assert sorted(fc_fs_set) == sorted(expected_fs_set)
