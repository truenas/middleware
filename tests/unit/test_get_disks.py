import json
import subprocess
import uuid

from middlewared.utils.disks_.get_disks import get_disks

import pytest


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
            assert a.size_bytes == b["size"] * a.sector_info.logical_sector_size

    assert at_least_one, "No disks with partitions! (or get_disks() failed)"
