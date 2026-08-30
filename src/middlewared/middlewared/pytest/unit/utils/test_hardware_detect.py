"""Coverage for the moved platform detector.

Everything here drives ``detect_platform`` through its four impure inputs --
DMI, udev, the SES enclosure enumeration and ``ipmi-raw`` -- with stand-ins.
The paths that cannot be reached that way are called out in the tests that get
closest to them.
"""

from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest
from ixhardware import DMIInfo

from middlewared.utils.hardware import detect


@pytest.fixture(autouse=True)
def uncached():
    """``detect_platform`` is ``@cache``d, so a stale entry from one test
    would answer for the next one."""
    detect.detect_platform.cache_clear()
    yield
    detect.detect_platform.cache_clear()


@pytest.fixture
def dmi(monkeypatch):
    def build(**kwargs):
        monkeypatch.setattr(detect, "parse_dmi", lambda: DMIInfo(**kwargs))

    return build


@dataclass
class FakeEnclosure:
    """Stands in for ``enclosure_class.Enclosure`` at the attributes the
    detector reads."""

    product: str = ""
    vendor: str = ""
    is_mseries: bool = False
    is_xseries: bool = False
    pci: str = ""
    elements: dict = field(default_factory=dict)


@pytest.fixture
def enclosures(monkeypatch):
    def build(*encs: FakeEnclosure):
        monkeypatch.setattr(detect, "get_ses_enclosures", lambda asdict: list(encs))

    return build


def udev_device(attributes: dict):
    """Stand in for a ``pyudev.Device`` at the one thing the detector reads:
    ``.attributes.get('device/model')``. ``dict.get`` gives the real pyudev
    behavior for an attribute the device does not expose -- ``None``, not a
    ``KeyError``."""
    return SimpleNamespace(attributes=SimpleNamespace(get=attributes.get))


def backplane(model: bytes | str):
    """A scsi_generic device whose inquiry model is `model`."""
    return udev_device({"device/model": model})


@pytest.fixture
def udev(monkeypatch):
    """Replace the pyudev ``Context`` the detector constructs, so nothing
    talks to a real udev. Returns the list the queries are recorded into."""

    def build(*devices):
        queried: list[dict] = []

        class FakeContext:
            def list_devices(self, **kwargs):
                queried.append(kwargs)
                return list(devices)

        monkeypatch.setattr(detect, "Context", FakeContext)
        return queried

    return build


@pytest.fixture
def ipmi(monkeypatch):
    """Replace the whole ``subprocess`` module reference, so nothing can fork."""

    def build(stdout: bytes):
        calls: list[list[str]] = []

        def run(argv, **kwargs):
            calls.append(argv)
            return SimpleNamespace(stdout=stdout)

        monkeypatch.setattr(detect, "subprocess", SimpleNamespace(run=run, PIPE=-1))
        return calls

    return build


# (a) No product name at all: nothing downstream has anything to work with, and the bail is
# checked before everything else.
def test_no_product_name_beats_the_qemu_stamp(dmi):
    """The empty-product bail is checked first, so even a stamped serial does
    not get as far as the QEMU branch."""
    dmi(system_manufacturer="QEMU", system_product_name="", system_serial_number="ha1")
    assert detect.detect_platform() == ("MANUAL", "MANUAL")


# (b) QEMU. The serial has to carry the HA stamp, and its last character
# assigns the node.
@pytest.mark.parametrize(
    "serial,node",
    [
        ("ha1", "A"),
        ("ha2", "B"),
        ("something_c1", "A"),
        ("something_c2", "B"),
    ],
)
def test_qemu_ha_serials(dmi, serial, node):
    dmi(system_manufacturer="QEMU", system_product_name="Standard PC", system_serial_number=serial)
    assert detect.detect_platform() == ("IXKVM", node)


@pytest.mark.parametrize("serial", ["abc123", "HA1"])
def test_qemu_without_the_ha_stamp(dmi, serial):
    """TrueNAS is installed in plain KVM constantly; only the stamp makes it
    one of ours."""
    dmi(system_manufacturer="QEMU", system_product_name="Standard PC", system_serial_number=serial)
    assert detect.detect_platform() == ("MANUAL", "MANUAL")


def test_qemu_stamp_wins_over_a_truenas_product_name(dmi):
    dmi(system_manufacturer="QEMU", system_product_name="TRUENAS-M50", system_serial_number="ha1")
    assert detect.detect_platform() == ("IXKVM", "A")


# (c) bhyve. The host attaches a scsi_generic device whose inquiry model names
# the controller position; finding it is the whole of the test, because that
# device is what separates an HA bhyve guest from an ordinary one.
@pytest.mark.parametrize("node,as_bytes", [("A", True), ("B", False)], ids=["bytes", "str"])
def test_bhyve_node_from_backplane_model(dmi, udev, node, as_bytes):
    """pyudev hands back bytes on some kernels and str on others, and the
    value carries trailing whitespace either way."""
    model = f"TrueNAS_{node}  \n"
    udev(backplane(model.encode() if as_bytes else model))
    dmi(system_product_name="BHYVE")
    assert detect.detect_platform() == ("BHYVE", node)


def test_bhyve_without_the_ha_backplane(dmi, udev):
    """An ordinary bhyve development guest has disks but no TrueNAS backplane,
    and must not be mistaken for one half of an HA pair."""
    udev(backplane(b"QEMU HARDDISK"), backplane("Virtual disk"))
    dmi(system_product_name="BHYVE")
    assert detect.detect_platform() == ("MANUAL", "MANUAL")


def test_bhyve_device_without_a_model_attribute_is_skipped(dmi, udev):
    """A device that exposes no ``device/model`` yields ``None``; that has to
    be stepped over, not treated as a model, or it aborts the scan before the
    real backplane further down the list."""
    udev(udev_device({}), udev_device({"device/vendor": b"iX"}), backplane(b"TrueNAS_B"))
    dmi(system_product_name="BHYVE")
    assert detect.detect_platform() == ("BHYVE", "B")


# (d) Anything that is neither QEMU nor a shipped platform prefix stops here,
# before any enclosure or BMC access is attempted. The enclosure stand-in
# raises to prove the walk is never reached.
@pytest.mark.parametrize("product", ["X11SSH-F", "truenas-m50"])
def test_non_platform_prefix_bails_early(dmi, monkeypatch, product):
    def explode(asdict):
        raise AssertionError("enclosures must not be walked on unknown hardware")

    monkeypatch.setattr(detect, "get_ses_enclosures", explode)
    dmi(system_manufacturer="Supermicro", system_product_name=product)
    assert detect.detect_platform() == ("MANUAL", "MANUAL")


# (e) V-Series: the digit after the prefix picks the codename, and the SES
# product suffix picks the node.
@pytest.mark.parametrize("product,hardware", [("TRUENAS-V100", "LUDICROUS"), ("TRUENAS-V260", "PLAID")])
def test_vseries_codename(dmi, enclosures, product, hardware):
    enclosures(FakeEnclosure(vendor="ECStream", product="4IXGA-NTBp"))
    dmi(system_product_name=product)
    assert detect.detect_platform() == (hardware, "A")


@pytest.mark.parametrize(
    "ses_product,node",
    [("4IXGA-NTBp", "A"), ("4IXGA-NTGp", "A"), ("4IXGA-NTBs", "B"), ("4IXGA-NTGs", "B")],
)
def test_vseries_node_from_backplane_suffix(dmi, enclosures, ses_product, node):
    """NTB is the original V-Series board, NTG the 4IXGA_PEX89032 one; both
    use the same -p/-s suffix for controller position."""
    enclosures(FakeEnclosure(vendor="ECStream", product=ses_product))
    dmi(system_product_name="TRUENAS-V260")
    assert detect.detect_platform() == ("PLAID", node)


def test_vseries_unknown_generation(dmi, enclosures):
    """A V3XX would not be recognized, and must not guess a codename."""
    enclosures(FakeEnclosure(vendor="ECStream", product="4IXGA-NTBp"))
    dmi(system_product_name="TRUENAS-V360")
    assert detect.detect_platform() == ("MANUAL", "MANUAL")


# (f) M-Series: the enclosure product names the controller position.
@pytest.mark.parametrize("ses_product,node", [("4024Sp", "A"), ("4024Ss", "B")])
def test_mseries_node(dmi, enclosures, ses_product, node):
    enclosures(FakeEnclosure(is_mseries=True, product=ses_product))
    dmi(system_product_name="TRUENAS-M50")
    assert detect.detect_platform() == ("ECHOWARP", node)


def test_mseries_without_a_recognized_backplane(dmi, enclosures):
    """The chassis is still an M-Series; only the node is unknown."""
    enclosures(FakeEnclosure(is_mseries=True, product="4024S"))
    dmi(system_product_name="TRUENAS-M50")
    assert detect.detect_platform() == ("ECHOWARP", "MANUAL")


# (g) H-Series: bit 0 of the MCU's tenth byte is set on the primary
# controller. The value is masked with 1, so only 0 and 1 can come out and
# the "unexpected value" guard in the function is unreachable from here.
@pytest.mark.parametrize(
    "stdout,node",
    [
        (b"01", "A"),
        (b"00", "B"),
        (b"0f", "A"),
        (b"0a", "B"),
        (b"00 00 00 03\n", "A"),
        (b"00 00 00 02\n", "B"),
    ],
)
def test_hseries_node_from_mcu(dmi, ipmi, stdout, node):
    ipmi(stdout)
    dmi(system_product_name="TRUENAS-H10")
    assert detect.detect_platform() == ("SUBLIGHT", node)


def test_hseries_with_a_silent_mcu(dmi, ipmi):
    ipmi(b"")
    dmi(system_product_name="TRUENAS-H10")
    assert detect.detect_platform() == ("SUBLIGHT", "MANUAL")


def test_hseries_asks_the_mcu_for_the_documented_register(dmi, ipmi):
    calls = ipmi(b"01")
    dmi(system_product_name="TRUENAS-H10")
    detect.detect_platform()
    assert calls == [["ipmi-raw", "0", "6", "52", "b", "b2", "9", "0"]]
