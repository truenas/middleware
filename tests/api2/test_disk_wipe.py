from middlewared.test.integration.utils import call
from middlewared.test.integration.assets.pool import another_pool


def test_disk_wipe_exported_zpool_in_disk_get_unused():
    tmp_pool_name = used_disks = None
    with another_pool() as tmp_pool:
        tmp_pool_name = tmp_pool['name']
        flat = call('pool.flatten_topology', tmp_pool['topology'])
        used_disks = [i['disk'] for i in flat if i['type'] == 'DISK']

    # something is way off if neither of these are set
    assert all((tmp_pool_name, used_disks))

    for disk in filter(lambda x: x['name'] in used_disks, call('disk.get_unused')):
        # disks should still show as being part of an exported zpool
        assert disk['exported_zpool'] == tmp_pool_name

        # since we're here we'll wipe the disks
        call('disk.wipe', disk['name'], 'QUICK', job=True)

    for disk in filter(lambda x: x['name'] in used_disks, call('disk.get_unused')):
        # now disks should no longer show as being part of the exported zpool
        assert disk['exported_zpool'] is None
