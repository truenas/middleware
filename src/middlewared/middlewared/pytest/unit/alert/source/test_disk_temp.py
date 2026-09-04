from types import SimpleNamespace

import pytest

from middlewared.alert.source.disk_temp import (
    DiskTemperatureAboveDefaultLimitAlert,
    DiskTemperatureTooHotAlert,
    DiskTemperatureTooHotAlertSource,
)
from middlewared.pytest.unit.middleware import Middleware


def _source(rotational, temp, crit, max_):
    m = Middleware()
    m["disk.get_disks"] = lambda: [
        SimpleNamespace(name="sda", serial="AAAABBBBCCCCDDDD", rotational=rotational)
    ]
    m["disk.temperature_entries"] = lambda names: {"sda": (temp, crit, max_)}
    return DiskTemperatureTooHotAlertSource(m)


# ---------------------------------------------------------------------------
# Disks that report a critical temperature of their own: unchanged behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_alert_below_reported_crit():
    assert await _source(True, 35, 70, 55).check() == []


@pytest.mark.asyncio
async def test_reported_crit_alerts_with_the_reported_value():
    alerts = await _source(True, 71, 70, 55).check()
    assert len(alerts) == 1
    assert isinstance(alerts[0].instance, DiskTemperatureTooHotAlert)
    assert alerts[0].instance.crit_threshold == 70


@pytest.mark.asyncio
async def test_reported_crit_is_inclusive():
    """The pre-existing comparison is `temp >= crit`, not `>`."""
    alerts = await _source(True, 70, 70, 55).check()
    assert len(alerts) == 1
    assert isinstance(alerts[0].instance, DiskTemperatureTooHotAlert)


@pytest.mark.asyncio
async def test_recommended_maximum_alone_does_not_alert():
    """Exceeding the disk's own continuous operating maximum is not by itself
    an alerting condition; only the critical tier alerts."""
    assert await _source(True, 56, 70, 55).check() == []


# ---------------------------------------------------------------------------
# Disks that report no usable critical temperature: absolute fallback
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "rotational,temp,expected_threshold",
    [
        (True, 60, 60),
        (True, 59, None),
        (False, 60, None),
        (False, 70, 70),
        # sysfs did not say: treated as rotational, i.e. the stricter threshold.
        (None, 60, 60),
    ],
)
@pytest.mark.asyncio
async def test_fallback_threshold_by_device_class(rotational, temp, expected_threshold):
    alerts = await _source(rotational, temp, None, None).check()
    if expected_threshold is None:
        assert alerts == []
    else:
        assert len(alerts) == 1
        assert isinstance(alerts[0].instance, DiskTemperatureAboveDefaultLimitAlert)
        assert alerts[0].instance.crit_threshold == expected_threshold


@pytest.mark.parametrize("crit", [0, -5])
@pytest.mark.asyncio
async def test_non_positive_reported_crit_falls_back(crit):
    alerts = await _source(True, 61, crit, None).check()
    assert len(alerts) == 1
    assert isinstance(alerts[0].instance, DiskTemperatureAboveDefaultLimitAlert)
    assert alerts[0].instance.crit_threshold == 60


@pytest.mark.asyncio
async def test_fallback_never_lands_below_reported_maximum():
    """A disk whose reported maximum continuous operating temperature is above
    the absolute fallback (e.g. the Seagate SAS default of 65C) must not be
    declared critical at 60C, or it would alert permanently."""
    assert await _source(True, 62, None, 65).check() == []
    assert await _source(True, 66, None, 65).check() == []

    alerts = await _source(True, 71, None, 65).check()
    assert len(alerts) == 1
    assert isinstance(alerts[0].instance, DiskTemperatureAboveDefaultLimitAlert)
    assert alerts[0].instance.crit_threshold == 70


@pytest.mark.asyncio
async def test_sas_reference_temperature_does_not_alert():
    """A NETAPP rebadged Seagate SAS disk reports a reference temperature of
    40C and idles at 46C. The reference temperature is a continuous operating
    limit, not a failure threshold, so this must not alert at all."""
    assert await _source(True, 46, None, 40).check() == []


@pytest.mark.asyncio
async def test_alert_key_ignores_temperature():
    """The dedup key must not include the temperature, or every degree of
    drift clears and re-raises the alert (and sends mail)."""
    a = (await _source(True, 61, None, None).check())[0]
    b = (await _source(True, 62, None, None).check())[0]
    assert a.key == b.key


# ---------------------------------------------------------------------------
# Degenerate input
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_temperature_no_alert():
    assert await _source(True, None, None, None).check() == []


@pytest.mark.asyncio
async def test_no_entry_no_alert():
    m = Middleware()
    m["disk.get_disks"] = lambda: [
        SimpleNamespace(name="sda", serial="AAAABBBBCCCCDDDD", rotational=True)
    ]
    m["disk.temperature_entries"] = lambda names: {"sda": None}
    assert await DiskTemperatureTooHotAlertSource(m).check() == []


@pytest.mark.asyncio
async def test_disk_disappeared_from_map():
    m = Middleware()
    m["disk.get_disks"] = lambda: []
    m["disk.temperature_entries"] = lambda names: {"sda": (99, None, None)}
    assert await DiskTemperatureTooHotAlertSource(m).check() == []
