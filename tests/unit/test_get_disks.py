import base64
import json
import subprocess
import uuid

from middlewared.utils.disks_.get_disks import get_disks
from truenas_api_client import Client

import pytest

VMFS_MAGIC_STRING_B64 = "DdABwA=="
VMFS_MAGIC_STRING_WFS = "VMFS_volume_member"


@pytest.mark.parametrize(
    "name,should_find", [(["sda"], True), (["/dev/sdb"], True), (["nope"], False)]
)
def test__get_disks_filters(name, should_find):
    found = False
    for i in get_disks(name_filters=name):
        found = i

    if should_find:
        assert found
    else:
        assert not found


def test__read_partitions():
    at_least_one = False
    for disk in get_disks():
        if not disk.parts:
            continue

        at_least_one = True
        sf = json.loads(
            subprocess.run(
                ["sfdisk", disk.devpath, "-J"], capture_output=True
            ).stdout.decode()
        )["partitiontable"]

        assert len(disk.partitions) == len(sf["partitions"])
        for a, b in zip(
            sorted(disk.partitions, key=lambda i: i.first_lba),
            sorted(sf["partitions"], key=lambda i: i["start"]),
        ):
            assert uuid.UUID(a.partition_type_guid) == uuid.UUID(b["type"])
            assert uuid.UUID(a.unique_partition_guid) == uuid.UUID(b["uuid"])
            assert a.first_lba == b["start"]
            assert a.last_lba == (b["start"] + b["size"]) - 1
            assert a.size_bytes == b["size"] * disk.lbs

    assert at_least_one, "No disks with partitions! (or get_disks() failed)"


def test__wipe_quick():
    with Client() as c:
        for disk_class in get_disks(
            name_filters=[c.call("disk.get_unused")[0]["name"]]
        ):
            disk = disk_class
            break
        else:
            assert False, "Failed to find an unused disk"

    # Wipe any existing partitions
    if disk.partitions:
        disk.wipe_quick()
        assert not disk.partitions

    # Fake a VMFS volume at start of disk
    with open(disk.devpath, "wb") as f:
        f.seek(1048576)
        f.write(base64.b64decode(VMFS_MAGIC_STRING_B64))

    fs = json.loads(
        subprocess.run(["wipefs", "-J", f"/dev/{disk}"], capture_output=True).stdout
    )["signatures"][0]
    assert fs["type"] == VMFS_MAGIC_STRING_WFS

    # Clean the drive
    disk.wipe_quick()
    fs = json.loads(
        subprocess.run(["wipefs", "-J", f"/dev/{disk}"], capture_output=True).stdout
    )["signatures"]
    assert not fs
