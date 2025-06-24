import base64
import json
import subprocess
import uuid

from middlewared.plugins.disk_.disk_info import DiskService
from truenas_api_client import Client

import pytest

VMFS_MAGIC_STRING_B64 = "DdABwA=="
VMFS_MAGIC_STRING_WFS = "VMFS_volume_member"


@pytest.mark.parametrize(
    "name,should_find", [(["sda"], True), (["/dev/sdb"], True), (["nope"], False)]
)
def test__get_disks_filters(name, should_find):
    found = False
    for i in DiskService(None).get_disks(name_filters=name):
        found = i

    if should_find:
        assert found
    else:
        assert not found


def test__read_partitions():
    at_least_one = False
    for disk in DiskService(None).get_disks():
        if not disk.partitions():
            continue

        at_least_one = True
        sf = json.loads(
            subprocess.run(
                ["sfdisk", disk.devpath, "-J"], capture_output=True
            ).stdout.decode()
        )["partitiontable"]

        assert len(disk.partitions()) == len(sf["partitions"])
        for a, b in zip(
            sorted(disk.partitions(), key=lambda i: i.first_lba),
            sorted(sf["partitions"], key=lambda i: i["start"]),
        ):
            assert uuid.UUID(a.partition_type_guid) == uuid.UUID(b["type"])
            assert uuid.UUID(a.unique_partition_guid) == uuid.UUID(b["uuid"])
            assert a.first_lba == b["start"]
            assert a.last_lba == (b["start"] + b["size"]) - 1

    assert at_least_one, "No disks with partitions! (or get_disks() failed)"


def test__wipe_quick():
    with Client() as c:
        for disk_class in DiskService(None).get_disks(
            name_filters=[c.call("disk.get_unused")[0]["name"]]
        ):
            disk = disk_class
            break
        else:
            assert False, "Failed to find an unused disk"

    # Wipe any existing partitions
    if disk.partitions():
        disk.wipe_quick()
        assert not disk.partitions()

    # Fake a VMFS volume at start of disk
    with open(disk.devpath, "wb") as f:
        f.seek(1048576)
        f.write(base64.b64decode(VMFS_MAGIC_STRING_B64))

    fs = json.loads(
        subprocess.run(["wipefs", "-J", disk.devpath], capture_output=True).stdout
    )["signatures"][0]
    assert fs["type"] == VMFS_MAGIC_STRING_WFS

    # Clean the drive
    disk.wipe_quick()
    fs = json.loads(
        subprocess.run(["wipefs", "-J", disk.devpath], capture_output=True).stdout
    )["signatures"]
    assert not fs


def test__format_disk():
    with Client() as c:
        unused_disks = c.call("disk.get_unused")
        if not unused_disks:
            pytest.skip("No unused disks available for testing")

        for disk_class in DiskService(None).get_disks(
            name_filters=[unused_disks[0]["name"]]
        ):
            disk = disk_class
            break
        else:
            assert False, "Failed to find an unused disk"

    # Format the disk with GPT partition table
    # Note: format() automatically wipes existing partitions if present
    partition_guid = disk.format()

    # Verify the partition GUID is valid UUID
    assert isinstance(partition_guid, uuid.UUID)

    # Verify the disk now has partitions
    assert disk.partitions() is not None
    assert len(disk.partitions()) == 1

    # Verify the partition has correct properties
    partition = disk.partitions()[0]
    assert partition.partition_type == "ZFS"
    assert partition.partition_name == "data"
    assert uuid.UUID(partition.unique_partition_guid) == partition_guid

    # Verify GPT structure using sfdisk
    sf = json.loads(
        subprocess.run(
            ["sfdisk", disk.devpath, "-J"], capture_output=True
        ).stdout.decode()
    )["partitiontable"]

    assert sf["label"] == "gpt"
    assert len(sf["partitions"]) == 1

    sfdisk_partition = sf["partitions"][0]
    assert uuid.UUID(sfdisk_partition["uuid"]) == partition_guid
    assert (
        sfdisk_partition["type"].lower() == "6a898cc3-1dd2-11b2-99a6-080020736631"
    )  # ZFS type GUID
    assert sfdisk_partition["name"] == "data"
