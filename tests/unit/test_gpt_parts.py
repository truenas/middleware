import json
import subprocess
import uuid

from middlewared.utils.disks_.get_disks import get_disks


def test__get_disks():
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

        assert len(disk.parts) == len(sf["partitions"])
        for a, b in zip(
            sorted(disk.parts, key=lambda i: i.first_lba),
            sorted(sf["partitions"], key=lambda i: i["start"]),
        ):
            assert uuid.UUID(a.partition_type_guid) == uuid.UUID(b["type"])
            assert uuid.UUID(a.unique_partition_guid) == uuid.UUID(b["uuid"])
            assert a.first_lba == b["start"]
            assert a.last_lba == (b["start"] + b["size"]) - 1
            assert a.size_bytes == b["size"] * a.sector_info.logical_sector_size

    assert at_least_one, "No disks with partitions! (or get_disks() failed)"
