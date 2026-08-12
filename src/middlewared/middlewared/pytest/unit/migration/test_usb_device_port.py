"""Exercise the USB port migration against a stubbed USB topology."""

import asyncio
import importlib.util
import logging
from pathlib import Path

import pytest


MIGRATION_PATH = Path(__file__).parents[3] / "migration" / "0021_usb_device_port.py"

# What is plugged in while the migration runs: port name -> (bus, device number).
PLUGGED_IN = {
    "usb_1_1": ("1", "2"),
    "usb_1_4": ("1", "3"),
    "usb_2_5": ("2", "4"),
    # The one device whose port and device number spell the same name.
    "usb_3_2": ("3", "2"),
}


@pytest.fixture
def migration():
    spec = importlib.util.spec_from_file_location("usb_device_port", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    module.get_all_usb_devices = lambda: {name: {} for name in PLUGGED_IN}
    module.find_usb_device_name_by_bus_and_devnum = lambda bus, devnum: next(
        (name for name, address in PLUGGED_IN.items() if address == (bus, devnum)), None
    )
    return module


class FakeMiddleware:
    def __init__(self, rows):
        self.rows = rows
        self.updates = []
        self.logger = logging.getLogger("test_usb_device_port")

    async def call(self, method, *args):
        if method == "datastore.query":
            return [dict(row, attributes=dict(row["attributes"])) for row in self.rows[args[0]]]
        if method == "datastore.update":
            datastore, id_, payload = args
            self.updates.append((datastore, id_, payload["attributes"]))
            return id_
        raise AssertionError(f"unexpected call {method}")

    async def run_in_thread(self, fn, *args):
        return fn(*args)


def _run(migration, container_rows=(), vm_rows=()):
    middleware = FakeMiddleware({"container.device": list(container_rows), "vm.device": list(vm_rows)})
    asyncio.run(migration.migrate(middleware))
    return middleware.updates


def _usb(id_, device, **extra):
    return {"id": id_, "attributes": {"dtype": "USB", "device": device, "usb": None, **extra}}


def test_container_device_number_is_converted_to_its_port(migration):
    # usb_1_3 was written as bus 1, device number 3, which is plugged into port 1-4.
    assert _run(migration, container_rows=[_usb(1, "usb_1_3")]) == [
        ("container.device", 1, {"dtype": "USB", "device": "usb_1_4", "usb": None}),
    ]


def test_container_name_that_also_reads_as_a_port_is_still_converted(migration):
    """`usb_1_2` is a live port name, but a container row can only ever be a device number."""
    assert _run(migration, container_rows=[_usb(1, "usb_1_2")]) == [
        ("container.device", 1, {"dtype": "USB", "device": "usb_1_1", "usb": None}),
    ]


def test_vm_name_that_already_names_an_occupied_port_is_left_alone(migration):
    assert _run(migration, vm_rows=[_usb(1, "usb_1_4", controller_type="nec-xhci")]) == []


def test_vm_name_that_names_no_port_falls_back_to_the_device_number(migration):
    # Nothing is plugged into port 1-3, but bus 1 device number 3 is port 1-4.
    assert _run(migration, vm_rows=[_usb(1, "usb_1_3", controller_type="nec-xhci")]) == [
        ("vm.device", 1, {"dtype": "USB", "device": "usb_1_4", "usb": None, "controller_type": "nec-xhci"}),
    ]


def test_unresolvable_row_is_left_alone_and_logged(migration, caplog):
    with caplog.at_level(logging.WARNING, logger="test_usb_device_port"):
        assert _run(migration, vm_rows=[_usb(1, "usb_9_9")]) == []

    assert "nothing is plugged into bus 9 device 9" in caplog.text


def test_name_that_parses_as_neither_is_left_alone_and_logged(migration, caplog):
    with caplog.at_level(logging.WARNING, logger="test_usb_device_port"):
        assert _run(migration, container_rows=[_usb(1, "usb_usb1")]) == []

    assert "names neither a port nor a bus and device number" in caplog.text


@pytest.mark.parametrize(
    "row",
    [
        # Identified by vendor and product ids, so it names no port at all.
        {
            "id": 1,
            "attributes": {"dtype": "USB", "device": None, "usb": {"vendor_id": "0x0bda", "product_id": "0x8153"}},
        },
        # A controller with nothing attached to it.
        {"id": 2, "attributes": {"dtype": "USB", "device": None, "usb": None}},
        {"id": 3, "attributes": {"dtype": "NIC", "nic_attach": "br0"}},
    ],
)
def test_rows_without_a_stored_device_are_untouched(migration, row):
    assert _run(migration, container_rows=[row], vm_rows=[row]) == []


def test_row_already_pointing_at_its_port_is_not_rewritten(migration):
    """A row whose device number resolves back to the same name needs no write."""
    assert _run(migration, container_rows=[_usb(1, "usb_3_2")]) == []


def test_migration_is_a_no_op_the_second_time(migration):
    middleware = FakeMiddleware(
        {
            "container.device": [_usb(1, "usb_1_3")],
            "vm.device": [_usb(2, "usb_1_3", controller_type="nec-xhci")],
        }
    )

    asyncio.run(migration.migrate(middleware))
    assert len(middleware.updates) == 2

    for datastore, id_, attributes in middleware.updates:
        for row in middleware.rows[datastore]:
            if row["id"] == id_:
                row["attributes"] = attributes

    middleware.updates.clear()
    asyncio.run(migration.migrate(middleware))
    assert middleware.updates == []
