import time

from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.assets.pool import another_pool


def test_disk_wipe_exported_zpool_in_disk_get_unused():
    with another_pool() as tmp_pool:
        tmp_pool_name = tmp_pool['name']
        flat = call('pool.flatten_topology', tmp_pool['topology'])
        used_disks = [i['disk'] for i in flat if i['type'] == 'DISK']

    for disk in filter(lambda x: x['name'] in used_disks, call('disk.get_unused')):
        # disks should still show as being part of an exported zpool
        assert disk['exported_zpool'] == tmp_pool_name

        # since we're here we'll wipe the disks
        call('disk.wipe', disk['name'], 'QUICK', job=True)

    for disk in filter(lambda x: x['name'] in used_disks, call('disk.get_unused')):
        # now disks should no longer show as being part of the exported zpool
        assert disk['exported_zpool'] is None


def test_disk_wipe_abort():
    disk = call("disk.get_unused")[0]["name"]

    job_id = call("disk.wipe", disk, "FULL")

    # Wait for wipe process to actually start
    for i in range(20):
        job = call("core.get_jobs", [["id", "=", job_id]], {"get": True})
        if job["progress"]["percent"] > 0:
            break

        time.sleep(0.1)
    else:
        assert False, job

    call("core.job_abort", job_id)

    for i in range(20):
        result = ssh(f"fuser /dev/{disk}", check=False, complete_response=True)
        # Fuser returns 1 when no other process is using the disk
        # (which means that the abort was completed successfully)
        if result["returncode"] == 1:
            # Ensure that the job was aborted before completion
            job = call("core.get_jobs", [["id", "=", job_id]], {"get": True})
            assert job["state"] == "ABORTED"
            assert job["progress"]["percent"] < 95
            break

        time.sleep(0.1)
    else:
        assert False, result
