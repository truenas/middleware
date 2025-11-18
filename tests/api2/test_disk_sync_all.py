import threading
from unittest.mock import ANY

from middlewared.test.integration.utils import call, client
from middlewared.test.integration.utils.mock import mock
from middlewared.test.integration.utils.mock_db import mock_table_contents

SDA = {
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
}
SDA_IDENTIFIER = "{serial_lunid}202509064119_5000000000000001"


def test_disk_sync():
    with mock_table_contents(
        "storage.disk",
        [],
    ):
        with client() as c:
            received = []
            event = threading.Event()

            def append(type, **kwargs):
                received.append(kwargs)
                event.set()

            c.subscribe("disk.query", append)

            # added event

            with mock("device.get_disks", return_value={
                "sda": SDA,
            }):
                call("disk.sync", "sda")

            event.wait(10)
            assert received == [
                {
                    "collection": "disk.query",
                    "msg": "added",
                    "id": SDA_IDENTIFIER,
                    "fields": ANY,
                }
            ]
            assert received[0]["fields"]["name"] == "sda"

            # changed event

            received.clear()
            event.clear()

            with mock("device.get_disks", return_value={
                "sdb": {**SDA, "name": "sdb"},
            }):
                call("disk.sync", "sdb")

            event.wait(10)
            assert received == [
                {
                    "collection": "disk.query",
                    "msg": "changed",
                    "id": SDA_IDENTIFIER,
                    "fields": ANY,
                }
            ]
            assert received[0]["fields"]["name"] == "sdb"


def test_disk_sync_all():
    with mock_table_contents(
        "storage.disk",
        [],
    ):
        with client() as c:
            received = []
            event = threading.Event()

            def append(type, **kwargs):
                received.append(kwargs)
                event.set()

            c.subscribe("disk.query", append)

            # added event

            with mock("device.get_disks", return_value={
                "sda": SDA,
            }):
                call("disk.sync_all", job=True)

            event.wait(10)
            assert received == [
                {
                    "collection": "disk.query",
                    "msg": "added",
                    "id": SDA_IDENTIFIER,
                    "fields": ANY,
                }
            ]
            assert received[0]["fields"]["name"] == "sda"

            # changed event

            received.clear()
            event.clear()

            with mock("device.get_disks", return_value={
                "sdb": {**SDA, "name": "sdb"},
            }):
                call("disk.sync_all", job=True)

            event.wait(10)
            assert received == [
                {
                    "collection": "disk.query",
                    "msg": "changed",
                    "id": SDA_IDENTIFIER,
                    "fields": ANY,
                }
            ]
            assert received[0]["fields"]["name"] == "sdb"

            # removed event

            received.clear()
            event.clear()

            with mock("device.get_disks", return_value={}):
                call("disk.sync_all", job=True)

            event.wait(10)
            assert received == [
                {
                    "collection": "disk.query",
                    "msg": "removed",
                    "id": SDA_IDENTIFIER,
                }
            ]


def test_disk_sync_all_non_unique_identifiers():
    with mock_table_contents(
        "storage.disk",
        [],
    ):
        with mock("device.get_disks", return_value={
            "sda": SDA,
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
                "ident": SDA["ident"],
                "serial": SDA["serial"],
                "model": "D4_SSD",
                "descr": "D4_SSD",
                "lunid": SDA["lunid"],
                "bus": "USB",
                "type": "SSD",
                "blocks": 7814037168,
                "serial_lunid": SDA["serial_lunid"],
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
        assert disks[0]["disk_identifier"] == SDA_IDENTIFIER
        # We also don't care about which of the disks with non-unique identifier will be present in the table
        assert disks[0]["disk_name"] in ["sda", "sdb"]
