"""Coverage for ``mseries.nvdimm.info``, fed what the second NVDIMM of an M60 answered.

That module's energy source is not cabled, so it reports all ones for it.
"""

import errno
import io
import stat
from types import SimpleNamespace

import pytest

from middlewared.plugins.hardware import m_series_nvdimm
from middlewared.pytest.unit.middleware import Middleware
from middlewared.utils.hardware import nvdimm

ANSWERS = {
    nvdimm.CRITICAL_HEALTH: bytes.fromhex("44"),
    nvdimm.MODULE_HEALTH: bytes.fromhex("000020000000630000"),
    nvdimm.ES_HEALTH: bytes.fromhex("ffffff00660000"),
}
REGISTERS = {
    nvdimm.SPECREV: 0x22,
    nvdimm.FW_SLOT_INFO: 0x11,
    nvdimm.SLOT_FWREV_HIGH[1]: 0x08,
}
SYSFS = {
    "vendor": "0x01ce",
    "device": "0x394e",
    "rev_id": "0x3400",
    "subsystem_vendor": "0x80c1",
    "subsystem_device": "0x3143",
    "subsystem_rev_id": "0x0100",
}


@pytest.fixture
def m60(monkeypatch):
    """One NVDIMM at ``/dev/nmem1``. Yields the requests sent to it and the descriptors closed."""
    sent: list = []
    closed: list = []

    class Device:
        def fileno(self):
            return 3

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            closed.append(self.fileno())

    def dsm(fd, func, data=b"", *, need=1, out_size=32):
        sent.append(func)
        return ANSWERS[func]

    def i2c_read(fd, page, off):
        sent.append((page, off))
        return REGISTERS[(page, off)]

    class Scan(list):
        """Stands in for what ``os.scandir`` returns, which is also a context manager."""

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return None

    def entry(name, mode):
        return SimpleNamespace(name=name, path=f"/dev/{name}", stat=lambda: SimpleNamespace(st_mode=mode))

    # Only the first entry is an NVDIMM. The others have the right name or the right type, not both.
    listing = Scan([entry("nmem1", stat.S_IFCHR), entry("nmem1.bak", stat.S_IFREG), entry("null", stat.S_IFCHR)])

    def fake_open(path, mode="r", buffering=-1):
        """Stands in for ``open`` on the NVDIMM itself and on its id files in sysfs."""
        if path.startswith("/sys/"):
            return io.StringIO(SYSFS[path.rsplit("/", 1)[1]] + "\n")
        return Device()

    monkeypatch.setattr(m_series_nvdimm, "os", SimpleNamespace(scandir=lambda path: listing))
    monkeypatch.setattr(m_series_nvdimm, "open", fake_open, raising=False)
    monkeypatch.setattr(m_series_nvdimm, "state_flags", lambda nmem: ["smart_notify"])
    monkeypatch.setattr(nvdimm, "dsm", dsm)
    monkeypatch.setattr(nvdimm, "i2c_read", i2c_read)

    # ``static_info`` is ``@cache``d, so a stale entry from one test would answer for the next one
    m_series_nvdimm.static_info.cache_clear()
    yield SimpleNamespace(sent=sent, closed=closed)
    m_series_nvdimm.static_info.cache_clear()


def service() -> m_series_nvdimm.MseriesNvdimmService:
    m = Middleware()
    m["truenas.get_chassis_hardware"] = lambda: "TRUENAS-M60"
    return m_series_nvdimm.MseriesNvdimmService(m)


def test_info_matches_what_ixnvdimm_reported(m60):
    (info,) = service().info()

    assert (info["index"], info["dev"], info["dev_path"]) == (1, "nmem1", "/dev/nmem1")
    assert info["specrev"] == 22
    assert info["state_flags"] == ["smart_notify"]
    assert info["critical_health_info"] == {"0x44": ["PERSISTENCY_RESTORED"]}
    assert info["nvm_health_info"] == {"0x0000": []}
    assert info["nvm_error_threshold_status"] == {"0x00": []}
    assert info["nvm_warning_threshold_status"] == {"0x00": []}
    assert (info["nvm_lifetime"], info["nvm_temperature"]) == ("99%", "32")
    assert (info["es_lifetime"], info["es_temperature"]) == ("-1%", "-255")
    assert (info["part_num"], info["qualified_firmware"]) == ("AGIGA8811-032ACA", ["0.8"])
    assert (info["running_firmware"], info["old_bios"]) == ("0.8", False)
    # Opened once for the values that get cached and once for health
    assert m60.closed == [3, 3]


def test_values_that_do_not_change_are_read_once(m60):
    svc = service()
    svc.info()
    m60.sent.clear()
    m60.closed.clear()

    svc.info()

    assert m60.sent == [nvdimm.CRITICAL_HEALTH, nvdimm.MODULE_HEALTH, nvdimm.ES_HEALTH]
    assert m60.closed == [3]


def test_failed_read_propagates_and_closes_the_device(m60, monkeypatch):
    def dsm(fd, func, data=b"", *, need=1, out_size=32):
        raise OSError(errno.EINVAL, "Invalid argument")

    monkeypatch.setattr(nvdimm, "dsm", dsm)

    with pytest.raises(OSError):
        service().info()

    # The cached values were read first and that worked. The health read failed.
    assert m60.closed == [3, 3]


def test_unreadable_running_slot_means_old_bios(m60, monkeypatch):
    """ixnvdimm printed no line for a slot above 1, which is what the old parser took for an old BIOS."""
    monkeypatch.setitem(REGISTERS, nvdimm.FW_SLOT_INFO, 0xF1)

    (info,) = service().info()

    assert (info["running_firmware"], info["old_bios"]) == (None, True)


def test_each_flag_name_has_its_own_bit():
    assert m_series_nvdimm.bit_names(0x02, m_series_nvdimm.WARNING_THRESHOLD, 2) == {"0x02": ["ES_LIFETIME_WARNING"]}
    assert m_series_nvdimm.bit_names(0x4001, m_series_nvdimm.MODULE_HEALTH, 4) == {
        "0x4001": ["VOLTAGE_REGULATOR_FAILED", "ES_HEALTH_ASSESSMENT_ERROR"]
    }
