from typing import Any

from middlewared.alert.source.mseries_nvdimm_and_bios import (
    NVDIMMAlert,
    NVDIMMAndBIOSAlertSource,
    NVDIMMInvalidFirmwareVersionAlert,
    NVDIMMMemoryModLifetimeWarningAlert,
    NVDIMMRecommendedFirmwareVersionAlert,
    OldBiosVersionAlert,
)
from middlewared.plugins.hardware.m_series_nvdimm import NvdimmInfo
from middlewared.pytest.unit.middleware import Middleware


def _nvdimm(**overrides: Any) -> NvdimmInfo:
    """A healthy NVDIMM that on its own produces no alerts; override fields per test."""
    base: dict[str, Any] = dict(
        index=0,
        dev="nmem0",
        dev_path="/dev/nmem0",
        specrev=21,
        state_flags=[],
        critical_health_info={},
        nvm_health_info={},
        nvm_error_threshold_status={},
        nvm_warning_threshold_status={},
        nvm_lifetime="99%",
        nvm_temperature="40",
        es_lifetime="99%",
        es_temperature="40",
        vendor=None,
        device=None,
        rev_id=None,
        subvendor=None,
        subdevice=None,
        subrev_id=None,
        part_num=None,
        size=None,
        clock_speed=None,
        qualified_firmware=["2.6"],
        recommended_firmware="2.6",
        running_firmware="2.6",
        old_bios=False,
    )
    base.update(overrides)
    return NvdimmInfo(**base)


def _produce(nvdimm: NvdimmInfo, old_bios: bool = False) -> list:
    source = NVDIMMAndBIOSAlertSource(Middleware())
    alerts: list = []
    source.produce_alerts(nvdimm, alerts, old_bios)
    return alerts


def test_healthy_nvdimm_produces_no_alerts():
    assert _produce(_nvdimm()) == []


def test_low_memory_module_lifetime_alert():
    alerts = _produce(_nvdimm(nvm_lifetime="15%"))
    assert len(alerts) == 1, alerts
    assert isinstance(alerts[0].instance, NVDIMMMemoryModLifetimeWarningAlert)
    assert alerts[0].instance.value == 15


def test_running_firmware_not_qualified_alert():
    alerts = _produce(_nvdimm(running_firmware="1.0", qualified_firmware=["2.6"]))
    assert len(alerts) == 1, alerts
    assert isinstance(alerts[0].instance, NVDIMMInvalidFirmwareVersionAlert)


def test_running_firmware_below_recommended_alert():
    alerts = _produce(
        _nvdimm(
            running_firmware="2.6",
            qualified_firmware=["2.6", "3.0"],
            recommended_firmware="3.0",
        )
    )
    assert len(alerts) == 1, alerts
    instance = alerts[0].instance
    assert isinstance(instance, NVDIMMRecommendedFirmwareVersionAlert)
    assert instance.rv == "2.6"
    assert instance.uv == "3.0"


def test_not_armed_state_flag_alert():
    alerts = _produce(_nvdimm(state_flags=["not_armed"]))
    assert len(alerts) == 1, alerts
    assert isinstance(alerts[0].instance, NVDIMMAlert)
    assert alerts[0].instance.status == "NOT ARMED"


def test_critical_health_info_bit_alert():
    alerts = _produce(_nvdimm(critical_health_info={"0x2": ["some_failure"]}))
    assert len(alerts) == 1, alerts
    assert isinstance(alerts[0].instance, NVDIMMAlert)
    assert alerts[0].instance.value == "0x2"
    assert alerts[0].instance.status == "some_failure"


def test_old_bios_flag_alert():
    alerts = _produce(_nvdimm(old_bios=True), old_bios=False)
    assert len(alerts) == 1, alerts
    assert isinstance(alerts[0].instance, OldBiosVersionAlert)
