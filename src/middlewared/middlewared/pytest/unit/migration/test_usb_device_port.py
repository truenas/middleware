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
    module.usb_device_names_by_bus_and_devnum = lambda: {address: name for name, address in PLUGGED_IN.items()}
    return module


class FakeMiddleware:
    def __init__(self, rows, fail_updates=()):
        self.rows = rows
        self.fail_updates = set(fail_updates)
        self.updates = []
        self.logger = logging.getLogger("test_usb_device_port")

    async def call(self, method, *args):
        if method == "datastore.query":
            return [dict(row, attributes=dict(row["attributes"])) for row in self.rows[args[0]]]
        if method == "datastore.update":
            datastore, id_, payload = args
            if id_ in self.fail_updates:
                raise RuntimeError("datastore is unhappy")
            self.updates.append((datastore, id_, payload["attributes"]))
            return id_
        raise AssertionError(f"unexpected call {method}")

    async def run_in_thread(self, fn, *args):
        return fn(*args)


def _run(migration, container_rows=(), vm_rows=()):
    middleware = FakeMiddleware({"container.device": list(container_rows), "vm.device": list(vm_rows)})
    asyncio.run(migration.migrate(middleware))
    return middleware.updates


def _usb(id_, device, parent="vm", instance=1, **extra):
    """A USB device row as `datastore.query` returns it, instance joined in and all."""
    return {
        "id": id_,
        "attributes": {"dtype": "USB", "device": device, "usb": None, **extra},
        parent: {"id": instance, "name": f"instance-{instance}"},
    }


def _container(id_, device, **kwargs):
    return _usb(id_, device, parent="container", **kwargs)


def test_container_device_number_is_converted_to_its_port(migration):
    # usb_1_3 was written as bus 1, device number 3, which is plugged into port 1-4.
    assert _run(migration, container_rows=[_container(1, "usb_1_3")]) == [
        ("container.device", 1, {"dtype": "USB", "device": "usb_1_4", "usb": None}),
    ]


def test_container_name_that_also_reads_as_a_port_is_still_converted(migration):
    """`usb_1_2` is a live port name, but a container row can only ever be a device number."""
    assert _run(migration, container_rows=[_container(1, "usb_1_2")]) == [
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
        assert _run(migration, container_rows=[_container(1, "usb_usb1")]) == []

    assert "names neither a port nor a bus and device number" in caplog.text


@pytest.mark.parametrize(
    "attributes",
    [
        # Identified by vendor and product ids, so it names no port at all.
        {"dtype": "USB", "device": None, "usb": {"vendor_id": "0x0bda", "product_id": "0x8153"}},
        # A controller with nothing attached to it.
        {"dtype": "USB", "device": None, "usb": None},
        {"dtype": "NIC", "nic_attach": "br0"},
    ],
)
def test_rows_without_a_stored_device_are_untouched(migration, attributes):
    row = {"id": 1, "attributes": attributes, "vm": {"id": 1, "name": "instance-1"}}
    container_row = {"id": 1, "attributes": attributes, "container": {"id": 1, "name": "instance-1"}}
    assert _run(migration, container_rows=[container_row], vm_rows=[row]) == []


def test_row_already_pointing_at_its_port_is_not_rewritten(migration):
    """A row whose device number resolves back to the same name needs no write."""
    assert _run(migration, container_rows=[_container(1, "usb_3_2")]) == []


def test_migration_is_a_no_op_the_second_time(migration):
    middleware = FakeMiddleware(
        {
            "container.device": [_container(1, "usb_1_3")],
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


def test_rewrite_onto_a_port_an_untouched_row_holds_is_skipped(migration, caplog):
    """The row that is already correct keeps the port; the one that only resolves to it yields."""
    rows = [
        _usb(1, "usb_1_3", controller_type="nec-xhci"),  # bus 1 device 3 -> port 1-4
        _usb(2, "usb_1_4", controller_type="nec-xhci"),  # already port 1-4, left alone
    ]

    with caplog.at_level(logging.WARNING, logger="test_usb_device_port"):
        assert _run(migration, vm_rows=rows) == []

    assert "which device 2 already uses" in caplog.text
    assert "instance-1" in caplog.text


def test_rewrite_onto_a_port_an_unresolvable_row_holds_is_skipped(migration, caplog):
    """A row left alone keeps its stored name, so nothing may be renamed onto it.

    A container name is only ever a device number, so `usb_1_4` here means bus 1 device 4, which
    is plugged into nothing -- while port 1-4 itself holds the device bus 1 device 3 resolves to.
    """
    rows = [
        _container(1, "usb_1_4"),  # bus 1 device 4 -> nothing; left reading usb_1_4
        _container(2, "usb_1_3"),  # bus 1 device 3 -> port 1-4
    ]

    with caplog.at_level(logging.WARNING, logger="test_usb_device_port"):
        assert _run(migration, container_rows=rows) == []

    assert "which device 1 already uses" in caplog.text


def test_the_row_that_yields_does_not_depend_on_the_order_rows_are_read(migration):
    rows = [
        _usb(2, "usb_1_4", controller_type="nec-xhci"),
        _usb(1, "usb_1_3", controller_type="nec-xhci"),
    ]

    assert _run(migration, vm_rows=list(reversed(rows))) == _run(migration, vm_rows=rows) == []


def test_two_rewrites_onto_one_port_keep_the_lower_row(migration, caplog):
    """Nothing is already correct here, so the first row by id claims the port."""
    rows = [
        _usb(5, "usb_001_003", controller_type="nec-xhci"),  # padded, same pair as below
        _usb(9, "usb_1_3", controller_type="nec-xhci"),
    ]

    with caplog.at_level(logging.WARNING, logger="test_usb_device_port"):
        updates = _run(migration, vm_rows=rows)

    assert updates == [
        ("vm.device", 5, {"dtype": "USB", "device": "usb_1_4", "usb": None, "controller_type": "nec-xhci"}),
    ]
    assert "which device 5 already uses" in caplog.text


def test_two_instances_may_each_claim_the_same_port(migration):
    """Sharing one device between two VMs is legal config -- only one of them may run at a time."""
    rows = [
        _usb(1, "usb_1_3", instance=1, controller_type="nec-xhci"),
        _usb(2, "usb_1_3", instance=2, controller_type="nec-xhci"),
    ]

    assert _run(migration, vm_rows=rows) == [
        ("vm.device", 1, {"dtype": "USB", "device": "usb_1_4", "usb": None, "controller_type": "nec-xhci"}),
        ("vm.device", 2, {"dtype": "USB", "device": "usb_1_4", "usb": None, "controller_type": "nec-xhci"}),
    ]


def test_a_row_whose_instance_is_gone_is_still_converted(migration):
    row = {"id": 1, "attributes": {"dtype": "USB", "device": "usb_1_3", "usb": None}, "vm": None}

    assert _run(migration, vm_rows=[row]) == [
        ("vm.device", 1, {"dtype": "USB", "device": "usb_1_4", "usb": None}),
    ]


def test_a_row_that_cannot_be_written_does_not_stop_the_rest(migration, caplog):
    """Letting the exception out would leave the migration unrecorded, so the whole thing would run
    again on the next boot against device numbers the kernel has since reissued."""
    middleware = FakeMiddleware(
        {
            "container.device": [],
            "vm.device": [
                _usb(1, "usb_1_3", instance=1, controller_type="nec-xhci"),
                _usb(2, "usb_2_4", instance=2, controller_type="nec-xhci"),
            ],
        },
        fail_updates={1},
    )

    with caplog.at_level(logging.ERROR, logger="test_usb_device_port"):
        asyncio.run(migration.migrate(middleware))

    assert middleware.updates == [
        ("vm.device", 2, {"dtype": "USB", "device": "usb_2_5", "usb": None, "controller_type": "nec-xhci"}),
    ]
    assert "failed to point USB device 'usb_1_3' at port 'usb_1_4'" in caplog.text
