import pytest
from datetime import datetime

from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.mock import mock
from middlewared.test.integration.utils.mock_db import mock_table_contents

DISK_TEMPLATE = {
    "disk_subsystem": "scsi",
    "disk_number": 2160,
    "disk_serial": "",
    "disk_lunid": None,
    "disk_size": "17179869184",
    "disk_description": "",
    "disk_transfermode": "Auto",
    "disk_hddstandby": "Always On",
    "disk_advpowermgmt": "Disabled",
    "disk_togglesmart": True,
    "disk_smartoptions": "",
    "disk_expiretime": None,
    "disk_enclosure_slot": None,
    "disk_passwd": "",
    "disk_critical": None,
    "disk_difference": None,
    "disk_informational": None,
    "disk_model": "VBOX_HARDDISK",
    "disk_rotationrate": None,
    "disk_type": "HDD",
    "disk_kmip_uid": None,
    "disk_zfs_guid": None,
    "disk_bus": "ATA"
}
pytestmark = pytest.mark.disk


def test_does_not_set_zfs_guid_for_expired_disk():
    with mock_table_contents(
        "storage.disk",
        [
            {**DISK_TEMPLATE, "disk_identifier": "{serial}1", "disk_name": "sda", "disk_expiretime": datetime.utcnow()},
            {**DISK_TEMPLATE, "disk_identifier": "{serial}2", "disk_name": "sda"},
        ],
    ):
        with mock("pool.flatten_topology", return_value=[
            {"type": "DISK", "disk": "sda", "guid": "guid1"},
        ]):
            call("disk.sync_zfs_guid", {
                "topology": "MOCK",
            })

            assert call(
                "datastore.query", "storage.disk", [["disk_identifier", "=", "{serial}1"]], {"get": True},
            )["disk_zfs_guid"] is None
            assert call(
                "datastore.query", "storage.disk", [["disk_identifier", "=", "{serial}2"]], {"get": True},
            )["disk_zfs_guid"] == "guid1"


def test_does_not_return_expired_disks_with_same_guid():
    with mock_table_contents(
        "storage.disk",
        [
            {**DISK_TEMPLATE, "disk_identifier": "{serial}1", "disk_name": "sda", "disk_expiretime": datetime.utcnow(),
             "disk_zfs_guid": "guid1"},
            {**DISK_TEMPLATE, "disk_identifier": "{serial}2", "disk_name": "sda", "disk_zfs_guid": "guid1"},
        ]
    ):
        assert call("disk.disk_by_zfs_guid", "guid1")["identifier"] == "{serial}2"
