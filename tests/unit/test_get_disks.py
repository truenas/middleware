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
        if not disk.partitions:
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
            assert disk.size_bytes == b["size"] * 512

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


def test__format():
    with Client() as c:
        for disk_class in get_disks(
            name_filters=[c.call("disk.get_unused")[0]["name"]]
        ):
            disk = disk_class
            break
        else:
            assert False, "Failed to find an unused disk"

    part_guid = disk.format()
    parts = disk.partitions
    assert len(parts) == 1
    assert parts[0].partition_number == 1
    assert parts[0].partition_type == "ZFS"
    assert parts[0].partition_type_guid == "6a898cc3-1dd2-11b2-99a6-080020736631"
    assert uuid.UUID(parts[0].unique_partition_guid) == part_guid
    assert parts[0].partition_name == "data"
    assert parts[0].first_lba * 512 == 1048576  # always start at 1MiB

    part_size_in_bytes = (512 * parts[0].first_lba) + (512 * parts[0].last_lba)
    buffer_at_end = disk.size_bytes - part_size_in_bytes
    one_percent_of_disk = 0.01 * disk.size_bytes
    twoish_gibibytes = 2254857830.4  # give some wiggle room ~2.1GiB
    # we should _ALWAYS_ have ~2GiB or ~1% (whicever is smaller)
    # buffer left at end of disk so users may replace disks of
    # equivalent model but nominal in size (because users buy
    # suspect hardware from suspect sellers)
    if one_percent_of_disk < twoish_gibibytes:
        assert buffer_at_end <= one_percent_of_disk
    else:
        assert buffer_at_end <= twoish_gibibytes
