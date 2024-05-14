import pytest
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


def test_disk_wipe_partition_clean():
    """
    Confirm we clean up around the middle partitions
    """
    signal_msg = "ix private data"

    disk = call("disk.get_unused")[0]["name"]

    # Create a data partition
    call('disk.format', disk)
    parts = call('disk.list_partitions', disk)
    seek_blk = parts[0]['start_sector']
    blk_size = int(parts[0]['start'] / parts[0]['start_sector'])

    # Write some private data into the start of the data partition
    ssh(
        f"echo '{signal_msg}' > junk;"
        f"dd if=junk bs={blk_size} count=1 oseek={seek_blk} of=/dev/{disk};"
        "rm -f junk"
    )

    # Confirm presence
    readback_presence = ssh(f"dd if=/dev/{disk} bs={blk_size} iseek={seek_blk} count=1").splitlines()[0]
    assert signal_msg in readback_presence

    # Clean the drive
    call('disk.wipe', disk, 'QUICK', job=True)

    # Confirm it's now clean
    readback_clean = ssh(f"dd if=/dev/{disk} bs={blk_size} iseek={seek_blk} count=1").splitlines()[0]
    assert signal_msg not in readback_clean

    # Confirm we have no partitions from middleware
    partitions = call('disk.list_partitions', disk)
    assert len(partitions) == 0

    # Confirm the kernel partition tables indicate no partitions
    proc_partitions = str(ssh('cat /proc/partitions'))
    # If the wipe is truly successful /proc/partitions should have a singular
    # entry for 'disk' in the table
    assert len([line for line in proc_partitions.splitlines() if disk in line]) == 1


@pytest.mark.parametrize('dev_name', ['BOOT', 'UNUSED', 'bogus', ''])
def test_disk_get_partitions_quick(dev_name):
    """
    dev_name:
        'BOOT'   - find a proper device that has partitions
        'UNUSED' - find a proper device that does not have partitons
    All others are failure tests.  All failures are properly handled
    and should return an empty dictionary
    """
    has_partitions = False
    if 'BOOT' == dev_name:
        dev_name = call('boot.get_disks')[0]
        has_partitions = True
    elif 'UNUSED' == dev_name:
        # NOTE: 'unused' disks typically have no partitions
        dev_name = call('disk.get_unused')[0]['name']

    parts = call('disk.get_partitions_quick', dev_name)
    assert has_partitions == (len(parts) > 0)


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
