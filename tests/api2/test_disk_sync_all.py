from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.mock import mock
from middlewared.test.integration.utils.mock_db import mock_table_contents


def test_disk_sync_all_non_unique_identifiers():
    with mock_table_contents(
        "storage.disk",
        [],
    ):
        with mock("device.get_disks", return_value={
            "sda": {
                "name": "sda",
                "sectorsize": 512,
                "number": 2048,
                "subsystem": "scsi",
                "driver": "sd",
                "hctl": "5:0:0:0",
                "size": 8001563222016,
                "mediasize": 8001563222016,
                "vendor": "TM",
                "ident": "202509064119",
                "serial": "202509064119",
                "model": "D4_SSD",
                "descr": "D4_SSD",
                "lunid": "5000000000000001",
                "bus": "USB",
                "type": "SSD",
                "blocks": 15628053168,
                "serial_lunid": "202509064119_5000000000000001",
                "rotationrate": None,
                "stripesize": None,
                "parts": [],
                "dif": False,
            },
            "sdb": {
                "name": "sdb",
                "sectorsize": 512,
                "number": 2064,
                "subsystem": "scsi",
                "driver": "sd",
                "hctl": "5:0:0:1",
                "size": 4000787030016,
                "mediasize": 4000787030016,
                "vendor": "TM",
                "ident": "202509064119",
                "serial": "202509064119",
                "model": "D4_SSD",
                "descr": "D4_SSD",
                "lunid": "5000000000000001",
                "bus": "USB",
                "type": "SSD",
                "blocks": 7814037168,
                "serial_lunid": "202509064119_5000000000000001",
                "rotationrate": None,
                "stripesize": None,
                "parts": [],
                "dif": False,
            },
        }):
            call("disk.sync_all", job=True)

        disks = call("datastore.query", "storage.disk")
        # Only one disk will be present, we don't care about the other
        assert len(disks) == 1
        assert disks[0]["disk_identifier"] == "{serial_lunid}202509064119_5000000000000001"
        # We also don't care about which of the disks with non-unique identifier will be present in the table
        assert disks[0]["disk_name"] in ["sda", "sdb"]
