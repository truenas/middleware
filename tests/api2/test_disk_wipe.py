import time

import pytest

from auto_config import ha
from middlewared.test.integration.utils import call, ssh


def test_disk_wipe_partition_clean():
    """Confirm we clean up around the middle partitions"""
    signal_msg = "ix private data"
    disk = call("disk.get_unused")[0]["name"]

    # Create a data partition
    call('disk.format', disk)
    parts = call('disk.list_partitions', disk)
    seek_blk = parts[0]['start_sector']
    blk_size = parts[0]['start'] // parts[0]['start_sector']

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
    """Test that we can sucessfully abort a disk.wipe job"""
    expected_pids = set()
    if ha:
        # In HA systems fenced may be using the disk.  Obtain the PID
        # so that we can ignore it.
        fenced_info = call('failover.fenced.run_info')
        if fenced_info['running']:
            expected_pids.add(str(fenced_info['pid']))

    # Obtain a disk to wipe
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
        result = set(ssh(f"fuser /dev/{disk}", check=False).strip().split())
        # Check that only the expected PIDs are using the disk
        # (which means that the abort was completed successfully)
        if result == expected_pids:
            # Ensure that the job was aborted before completion
            job = call("core.get_jobs", [["id", "=", job_id]], {"get": True})
            assert job["state"] == "ABORTED"
            assert job["progress"]["percent"] < 95
            break

        time.sleep(0.1)
    else:
        assert False, result
