import logging
from unittest.mock import AsyncMock, Mock

import pytest

from middlewared.api.current import ContainerDeviceNicAttachChoices, ContainerEntry
from middlewared.plugins.container import migrate as migrate_module
from middlewared.plugins.container.migrate import connected_usb_devices, resolve_usb_device, usb_id

MOUSE = ("0x046d", "0xc52b")
DONGLE = ("0x0bda", "0x8153")


def udev_entry(vendor_id, product_id, available=True, error=None):
    """One entry as `get_all_usb_devices` returns it, trimmed to the fields the index reads."""
    return {
        "capability": {"vendor_id": vendor_id, "product_id": product_id},
        "available": available,
        "error": error,
    }


# What is plugged in: a mouse in port 1-4, a dongle in port 2-5. Hubs never appear here, which is
# what makes a pair of ids naming one resolve to nothing.
PLUGGED_IN = {
    "usb_1_4": udev_entry(*MOUSE),
    "usb_2_5": udev_entry(*DONGLE),
}

# Two of the same dongle, listed in the order udev happened to return them.
TWIN_DONGLES = {
    "usb_2_5": udev_entry(*DONGLE),
    "usb_1_4": udev_entry(*DONGLE),
}


def scan(monkeypatch, devices):
    monkeypatch.setattr(migrate_module, "get_all_usb_devices", lambda: devices)
    return connected_usb_devices()


@pytest.fixture
def connected(monkeypatch):
    return scan(monkeypatch, PLUGGED_IN)


@pytest.fixture
def twins(monkeypatch):
    return scan(monkeypatch, TWIN_DONGLES)


def incus_usb(**fields):
    """A USB device as an incus manifest carries it; incus omits the keys it has no value for."""
    return {"type": "usb", **fields}


def resolve(device_data, connected, claimed=None):
    return resolve_usb_device(device_data, connected, claimed if claimed is not None else set())


@pytest.mark.parametrize(
    "value,expected",
    [
        # How incus writes them.
        ("046d", "0x046d"),
        ("C52B", "0xc52b"),
        # Already prefixed: prefixing again produced `0x0x046d`, which named no device and was
        # accepted by a pattern that only asks for a `0x` prefix.
        ("0x046d", "0x046d"),
        ("0X046D", "0x046d"),
    ],
)
def test_usb_id_is_prefixed_exactly_once(value, expected):
    assert usb_id(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        None,
        1,
        b"046d",
        # Too short, too long, not hex, and empty.
        "1d6",
        "01d6b",
        "zzzz",
        "",
    ],
)
def test_usb_id_rejects_what_is_not_an_id(value):
    assert usb_id(value) is None


def test_the_index_comes_out_of_one_scan(connected):
    assert connected == {MOUSE: ["usb_1_4"], DONGLE: ["usb_2_5"]}


def test_an_entry_without_usable_ids_is_not_indexed(monkeypatch):
    connected = scan(
        monkeypatch,
        {
            "usb_1_4": udev_entry(*MOUSE),
            "usb_2_5": udev_entry(None, None),
            "usb_3_1": udev_entry("0x0bda", "not-an-id"),
        },
    )

    assert connected == {MOUSE: ["usb_1_4"]}


@pytest.mark.parametrize(
    "available,error",
    [
        # pylibvirt sets both together when it cannot read a device's BUSNUM/DEVNUM; either one
        # alone is enough to keep the entry out, because either one alone is enough to make
        # pylibvirt refuse the device at start.
        (False, "Missing required USB device information: bus, device"),
        (False, None),
        (True, "USB device usb_2_5 not found"),
    ],
)
def test_an_entry_pylibvirt_cannot_use_is_not_indexed(monkeypatch, available, error):
    """Such a port fails to start with a message saying nothing is plugged into it, while something is."""
    connected = scan(
        monkeypatch,
        {
            "usb_1_4": udev_entry(*MOUSE),
            "usb_2_5": udev_entry(*DONGLE, available=available, error=error),
        },
    )

    assert connected == {MOUSE: ["usb_1_4"]}


def test_identical_devices_are_indexed_in_port_order(twins):
    """Sorted, not in udev order, so the device picked out of this list is the same one every time."""
    assert twins == {DONGLE: ["usb_1_4", "usb_2_5"]}


def test_the_scan_happens_exactly_once(monkeypatch):
    scans = 0

    def counting_scan():
        nonlocal scans
        scans += 1
        return PLUGGED_IN

    monkeypatch.setattr(migrate_module, "get_all_usb_devices", counting_scan)
    connected_usb_devices()

    assert scans == 1


def test_ids_resolve_to_the_port_holding_that_device(connected):
    payload, reason = resolve(incus_usb(vendorid="046d", productid="c52b"), connected)

    assert payload == {"dtype": "USB", "device": "usb_1_4", "usb": None}
    assert "usb_1_4" in reason


def test_a_bus_and_device_number_takes_no_part_in_resolution(connected):
    """Bus 2 device 4 is port usb_2_5 right now, and the ids name the device in usb_1_4."""
    payload, _ = resolve(incus_usb(busnum="2", devnum="4", vendorid="046d", productid="c52b"), connected)

    assert payload == {"dtype": "USB", "device": "usb_1_4", "usb": None}


def test_several_candidates_resolve_to_the_first_of_them(twins):
    payload, reason = resolve(incus_usb(busnum="2", devnum="4", vendorid="0bda", productid="8153"), twins)

    assert payload == {"dtype": "USB", "device": "usb_1_4", "usb": None}
    assert "the first free of 2 connected devices carrying them" in reason


def test_ids_matching_nothing_connected_are_stored_as_ids(connected):
    """The device is unplugged. The row still says what the user asked for and can still be edited."""
    payload, _ = resolve(incus_usb(busnum="1", devnum="3", vendorid="1234", productid="5678"), connected)

    assert payload == {
        "dtype": "USB",
        "usb": {"vendor_id": "0x1234", "product_id": "0x5678"},
        "device": None,
    }


@pytest.mark.parametrize(
    "fields",
    [
        # One id alone, with an address that happens to name a connected device.
        {"busnum": "1", "devnum": "3", "vendorid": "046d"},
        {"productid": "c52b"},
        # Both there, one of them not an id.
        {"vendorid": "046d", "productid": "zzzz"},
        {"vendorid": 1133, "productid": "c52b"},
        # Nothing to go on at all.
        {},
        {"busnum": "1", "devnum": "3"},
    ],
)
def test_a_device_without_both_ids_is_skipped(connected, fields):
    payload, reason = resolve(incus_usb(**fields), connected)

    assert payload is None
    assert reason == "does not carry both a usable vendor id and a usable product id"


def test_a_port_goes_to_the_first_device_that_reaches_it(connected):
    """One mouse is connected, so the second device of the pair has nothing left to take."""
    claimed = set()

    first, _ = resolve(incus_usb(vendorid="046d", productid="c52b"), connected, claimed)
    second, reason = resolve(incus_usb(vendorid="0x046D", productid="0xC52B"), connected, claimed)

    assert first == {"dtype": "USB", "device": "usb_1_4", "usb": None}
    assert second is None
    assert reason == (
        "carries vendor id 0x046d product id 0xc52b, and every one of the 1 connected devices "
        "carrying them is already taken by an earlier device of this container"
    )


def test_two_identical_devices_go_to_two_rows_rather_than_one(twins):
    """Both dongles are connected, so a container configured for both keeps both."""
    claimed = set()

    first, _ = resolve(incus_usb(vendorid="0bda", productid="8153"), twins, claimed)
    second, reason = resolve(incus_usb(vendorid="0bda", productid="8153"), twins, claimed)

    assert first == {"dtype": "USB", "device": "usb_1_4", "usb": None}
    assert second == {"dtype": "USB", "device": "usb_2_5", "usb": None}
    assert "usb_2_5" in reason


def test_a_third_device_runs_out_of_identical_devices_to_take(twins):
    claimed = set()

    for _ in range(2):
        resolve(incus_usb(vendorid="0bda", productid="8153"), twins, claimed)
    third, reason = resolve(incus_usb(vendorid="0bda", productid="8153"), twins, claimed)

    assert third is None
    assert reason == (
        "carries vendor id 0x0bda product id 0x8153, and every one of the 2 connected devices "
        "carrying them is already taken by an earlier device of this container"
    )


def test_a_pair_of_ids_goes_to_the_first_device_that_reaches_it(connected):
    claimed = set()

    first, _ = resolve(incus_usb(vendorid="1234", productid="5678"), connected, claimed)
    second, reason = resolve(incus_usb(vendorid="1234", productid="5678"), connected, claimed)

    assert first == {
        "dtype": "USB",
        "usb": {"vendor_id": "0x1234", "product_id": "0x5678"},
        "device": None,
    }
    assert second is None
    assert reason == (
        "carries vendor id 0x1234 product id 0x5678, which an earlier device of this container already took"
    )


class FakeJob:
    def __init__(self):
        self.logs = b""

    async def logs_fd_write(self, data):
        self.logs += data


LOGGER_NAME = "container.migrate.test"


def make_context():
    context = Mock()
    # A real logger, so the resolution record the migration writes is something a test can read.
    context.logger = logging.getLogger(LOGGER_NAME)

    async def fake_call2(target, *args, **kwargs):
        if target is context.s.container.device.nic_attach_choices:
            return ContainerDeviceNicAttachChoices(BRIDGE=[], MACVLAN=[])
        if target is context.s.container.device.gpu_choices:
            return {}
        raise AssertionError(f"unexpected call2 target: {target!r}")

    context.call2 = AsyncMock(side_effect=fake_call2)
    context.middleware.call = AsyncMock(return_value=None)
    return context


def container(id_, name):
    return ContainerEntry.model_construct(id=id_, name=name)


def inserted_devices(context):
    return [call.args[2] for call in context.middleware.call.call_args_list if call.args[0] == "datastore.insert"]


@pytest.mark.asyncio
async def test_migrate_devices_never_scans_udev_itself(monkeypatch, connected):
    scans = 0

    def counting_scan():
        nonlocal scans
        scans += 1
        return PLUGGED_IN

    monkeypatch.setattr(migrate_module, "get_all_usb_devices", counting_scan)

    manifest = {
        "config": {},
        "devices": {
            "mouse": incus_usb(vendorid="046d", productid="c52b"),
            "dongle": incus_usb(vendorid="0bda", productid="8153"),
        },
    }
    context = make_context()
    job = FakeJob()

    for container_id, name in ((1, "first"), (2, "second")):
        await migrate_module.migrate_devices(context, job, manifest, container(container_id, name), connected)

    assert scans == 0
    # The same port for both containers: what one container has claimed says nothing about what
    # another one may be configured for, only one of them can be running at a time anyway.
    assert inserted_devices(context) == [
        {"attributes": {"dtype": "USB", "device": "usb_1_4", "usb": None}, "container_id": 1},
        {"attributes": {"dtype": "USB", "device": "usb_2_5", "usb": None}, "container_id": 1},
        {"attributes": {"dtype": "USB", "device": "usb_1_4", "usb": None}, "container_id": 2},
        {"attributes": {"dtype": "USB", "device": "usb_2_5", "usb": None}, "container_id": 2},
    ]


@pytest.mark.asyncio
async def test_migrate_uses_one_scan_for_every_pool(monkeypatch):
    scans = 0

    def counting_scan():
        nonlocal scans
        scans += 1
        return PLUGGED_IN

    monkeypatch.setattr(migrate_module, "get_all_usb_devices", counting_scan)
    monkeypatch.setattr(migrate_module, "license_active", AsyncMock(return_value=True))

    context = make_context()
    context.middleware.call = AsyncMock(return_value=[{"id": 1, "pool": "tank", "storage_pools": "dozer"}])
    context.call2 = AsyncMock(return_value=[])

    passed = []

    async def fake_to_thread(f, *args):
        if f is migrate_module.migrate_specific_pool:
            passed.append(args[-1])
            return None
        return f(*args)

    context.to_thread = AsyncMock(side_effect=fake_to_thread)

    await migrate_module.migrate(context, FakeJob())

    assert scans == 1
    assert len(passed) == 2
    assert passed[0] is passed[1]
    assert passed[0] == {MOUSE: ["usb_1_4"], DONGLE: ["usb_2_5"]}


@pytest.mark.asyncio
async def test_a_device_without_both_ids_is_skipped_and_said_so(connected, caplog):
    manifest = {"config": {}, "devices": {"mystery": incus_usb(busnum="9", devnum="9")}}
    context = make_context()
    job = FakeJob()

    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        await migrate_module.migrate_devices(context, job, manifest, container(1, "first"), connected)

    assert inserted_devices(context) == []
    assert b"does not carry both a usable vendor id and a usable product id" in job.logs
    assert "incus USB device 'mystery'" in caplog.text


@pytest.mark.asyncio
async def test_a_second_device_reaching_a_claimed_port_is_skipped(connected):
    manifest = {
        "config": {},
        "devices": {
            "mouse": incus_usb(vendorid="046d", productid="c52b"),
            "mouse-again": incus_usb(vendorid="046d", productid="c52b"),
        },
    }
    context = make_context()
    job = FakeJob()

    await migrate_module.migrate_devices(context, job, manifest, container(1, "first"), connected)

    assert inserted_devices(context) == [
        {"attributes": {"dtype": "USB", "device": "usb_1_4", "usb": None}, "container_id": 1},
    ]
    assert b"is already taken by an earlier device of this container" in job.logs


@pytest.mark.asyncio
async def test_how_each_device_resolved_is_recorded(connected, caplog):
    mouse = incus_usb(busnum="1", devnum="3", vendorid="046d", productid="c52b")
    manifest = {"config": {}, "devices": {"mouse": mouse}}
    context = make_context()

    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        await migrate_module.migrate_devices(context, FakeJob(), manifest, container(1, "first"), connected)

    assert "container 'first': incus USB device 'mouse'" in caplog.text
    # The raw manifest fields go in even though only the ids are resolved from, so a wrong outcome
    # can be reconstructed from what the manifest actually said.
    assert "busnum='1' devnum='3' vendorid='046d' productid='c52b'" in caplog.text
    assert "resolved to port usb_1_4 by vendor id 0x046d product id 0xc52b" in caplog.text
