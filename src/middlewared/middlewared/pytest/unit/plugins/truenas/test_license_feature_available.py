from datetime import date
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from truenas_pydmi.models import TRUENAS_UNKNOWN
from truenas_pylicensed import LicenseType

from middlewared.plugins.container.info import license_active as container_license_active
from middlewared.plugins.docker.service_utils import license_active as docker_license_active
from middlewared.plugins.fc.fc import FCService
from middlewared.plugins.iscsi_.targets import iSCSITargetService
from middlewared.plugins.support import SupportService
from middlewared.plugins.system.product import SystemService
from middlewared.plugins.truenas.license import TrueNASLicenseService
from middlewared.plugins.truenas.license_utils import FeatureInfo, FeaturePolicy, LicenseInfo
from middlewared.plugins.vm.info import license_active as vm_license_active
from middlewared.pytest.unit.helpers import create_service
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service.context import ServiceContext
from middlewared.service_exception import ValidationErrors

PAST = date(2000, 1, 1)
FUTURE = date(2999, 1, 1)


def make_license(features):
    """Build a LicenseInfo. ``features`` is an iterable of ``(name, expires_at: date | None)``."""
    return LicenseInfo(
        id="x",
        type=LicenseType.ENTERPRISE_SINGLE,
        model=None,
        expires_at=None,
        features=[FeatureInfo(name=name, start_date=None, expires_at=expires_at) for name, expires_at in features],
        serials=[],
        enclosures={},
        contract_type=None,
    )


def license_service(m, info=None):
    """A real TrueNASLicenseService wired to mock middleware, with ``info_private`` stubbed.

    Registers ``feature_available`` both as a string-routed method (for consumers that call
    ``middleware.call``) and on the service container (for consumers that call via ``self.s``).
    """
    svc = create_service(m, TrueNASLicenseService)
    m["truenas.license.info_private"] = MagicMock(return_value=info)
    m["truenas.license.feature_available"] = svc.feature_available
    m.services.truenas.license.feature_available = svc.feature_available
    return svc


def make_context(m):
    return ServiceContext(m, logging.getLogger("test"))


# ---- A. feature_available policy matrix -------------------------------------------------------


@pytest.mark.parametrize(
    "info, expected",
    [
        (make_license([("VMS", None)]), True),  # present, perpetual
        (make_license([("DEDUP", None)]), False),  # absent
        (make_license([("VMS", PAST)]), False),  # present but expired
        (make_license([("VMS", FUTURE)]), True),  # present, future expiry
        (None, False),  # no license
    ],
)
@pytest.mark.asyncio
async def test_policy_any(info, expected):
    m = Middleware()
    svc = license_service(m, info)
    assert await svc.feature_available("VMS", FeaturePolicy.ANY) is expected


@pytest.mark.parametrize(
    "is_enterprise, licensed, expected",
    [
        (True, True, True),
        (False, True, False),
        (True, False, False),
        (False, False, False),
    ],
)
@pytest.mark.asyncio
async def test_policy_enterprise(is_enterprise, licensed, expected):
    m = Middleware()
    svc = license_service(m, make_license([("SUPPORT", None)] if licensed else []))
    m["system.is_enterprise"] = AsyncMock(return_value=is_enterprise)
    assert await svc.feature_available("SUPPORT", FeaturePolicy.ENTERPRISE) is expected


@pytest.mark.parametrize(
    "ha_capable, licensed, expected",
    [
        (False, False, True),
        (False, True, True),
        (True, False, False),
        (True, True, True),
    ],
)
@pytest.mark.asyncio
async def test_policy_ha_appliance(ha_capable, licensed, expected):
    m = Middleware()
    svc = license_service(m, make_license([("VMS", None)] if licensed else []))
    m["system.is_ha_capable"] = AsyncMock(return_value=ha_capable)
    assert await svc.feature_available("VMS", FeaturePolicy.HA_APPLIANCE) is expected


@pytest.mark.parametrize(
    "chassis, licensed, expected",
    [
        (TRUENAS_UNKNOWN, False, True),  # not iX hardware
        ("TRUENAS-MINI-3.0-X+", False, True),  # MINI is unrestricted
        ("F100", True, True),  # iX hardware, licensed
        ("F100", False, False),  # iX hardware, unlicensed
    ],
)
@pytest.mark.asyncio
async def test_policy_ix_hardware(chassis, licensed, expected):
    m = Middleware()
    svc = license_service(m, make_license([("APPS", None)] if licensed else []))
    m["truenas.get_chassis_hardware"] = AsyncMock(return_value=chassis)
    assert await svc.feature_available("APPS", FeaturePolicy.IX_HARDWARE) is expected


@pytest.mark.asyncio
async def test_policy_unknown_raises():
    m = Middleware()
    svc = license_service(m, make_license([("VMS", None)]))
    with pytest.raises(ValueError):
        await svc.feature_available("VMS", "bogus")


# ---- B. license is not consulted unless the gate is active ------------------------------------


@pytest.mark.asyncio
async def test_ha_appliance_skips_license_off_appliance():
    m = Middleware()
    svc = license_service(m, make_license([]))
    m["system.is_ha_capable"] = AsyncMock(return_value=False)
    assert await svc.feature_available("VMS", FeaturePolicy.HA_APPLIANCE) is True
    m["truenas.license.info_private"].assert_not_called()


@pytest.mark.parametrize("chassis", [TRUENAS_UNKNOWN, "TRUENAS-MINI-R"])
@pytest.mark.asyncio
async def test_ix_hardware_skips_license_off_ix(chassis):
    m = Middleware()
    svc = license_service(m, make_license([]))
    m["truenas.get_chassis_hardware"] = AsyncMock(return_value=chassis)
    assert await svc.feature_available("APPS", FeaturePolicy.IX_HARDWARE) is True
    m["truenas.license.info_private"].assert_not_called()


@pytest.mark.asyncio
async def test_enterprise_skips_license_on_community():
    m = Middleware()
    svc = license_service(m, make_license([("SUPPORT", None)]))
    m["system.is_enterprise"] = AsyncMock(return_value=False)
    assert await svc.feature_available("SUPPORT", FeaturePolicy.ENTERPRISE) is False
    m["truenas.license.info_private"].assert_not_called()


@pytest.mark.asyncio
async def test_active_gate_consults_license():
    m = Middleware()
    svc = license_service(m, make_license([("VMS", None)]))
    m["system.is_ha_capable"] = AsyncMock(return_value=True)
    assert await svc.feature_available("VMS", FeaturePolicy.HA_APPLIANCE) is True
    m["truenas.license.info_private"].assert_called()


# ---- C. consumers, end-to-end through the real method -----------------------------------------


@pytest.mark.parametrize(
    "ha_capable, licensed, expected",
    [
        (False, False, True),
        (False, True, True),
        (True, False, False),
        (True, True, True),
    ],
)
@pytest.mark.asyncio
async def test_vm_license_active(ha_capable, licensed, expected):
    m = Middleware()
    license_service(m, make_license([("VMS", None)] if licensed else []))
    m["system.is_ha_capable"] = AsyncMock(return_value=ha_capable)
    assert await vm_license_active(make_context(m)) is expected


@pytest.mark.parametrize(
    "ha_capable, licensed, expected",
    [
        (False, False, True),
        (False, True, True),
        (True, False, False),
        (True, True, True),
    ],
)
@pytest.mark.asyncio
async def test_docker_license_active(ha_capable, licensed, expected):
    m = Middleware()
    license_service(m, make_license([("APPS", None)] if licensed else []))
    m["system.is_ha_capable"] = AsyncMock(return_value=ha_capable)
    assert await docker_license_active(make_context(m)) is expected


@pytest.mark.parametrize(
    "chassis, licensed, expected",
    [
        (TRUENAS_UNKNOWN, False, True),
        ("TRUENAS-MINI-R", False, True),
        ("F100", True, True),
        ("F100", False, False),
    ],
)
@pytest.mark.asyncio
async def test_container_license_active(chassis, licensed, expected):
    m = Middleware()
    license_service(m, make_license([("APPS", None)] if licensed else []))
    m["truenas.get_chassis_hardware"] = AsyncMock(return_value=chassis)
    assert await container_license_active(make_context(m)) is expected


# ---- D. consumers, wiring (feature_available mocked to a boolean) -----------------------------


@pytest.mark.parametrize(
    "available, hba_present, expected",
    [
        (True, True, True),
        (False, True, False),
        (True, False, False),
        (False, False, False),
    ],
)
@pytest.mark.asyncio
async def test_fc_capable(available, hba_present, expected):
    m = Middleware()
    feature_available = MagicMock(return_value=available)
    m["truenas.license.feature_available"] = feature_available
    m["fc.hba_present"] = MagicMock(return_value=hba_present)
    svc = create_service(m, FCService)
    assert await svc.capable() is expected
    feature_available.assert_called_once_with("FIBRECHANNEL", FeaturePolicy.ENTERPRISE)


@pytest.mark.parametrize(
    "mode, available, has_error",
    [
        ("FC", False, True),
        ("FC", True, False),
        ("ISCSI", False, False),
    ],
)
@pytest.mark.asyncio
async def test_iscsi_target_fc_gate(mode, available, has_error):
    m = Middleware()
    m["datastore.query"] = MagicMock(return_value=[])
    m["truenas.license.feature_available"] = MagicMock(return_value=available)
    svc = create_service(m, iSCSITargetService)
    svc.validate_name = AsyncMock(return_value=None)
    verrors = ValidationErrors()
    data = {"name": "tgt0", "alias": None, "mode": mode, "groups": [], "auth_networks": []}
    await svc._iSCSITargetService__validate(verrors, data, "iscsi_create")
    messages = [e.errmsg for e in verrors.errors]
    assert ("Fibre Channel not enabled" in messages) is has_error


@pytest.mark.parametrize(
    "vendor, available, expected",
    [
        ("Dell", True, False),  # OEM vendor short-circuits before the license is consulted
        (None, True, True),
        (None, False, False),
    ],
)
@pytest.mark.asyncio
async def test_support_is_available(vendor, available, expected):
    m = Middleware()
    m["system.vendor.name"] = AsyncMock(return_value=vendor)
    m["truenas.license.feature_available"] = MagicMock(return_value=available)
    svc = create_service(m, SupportService)
    assert await svc.is_available() is expected


# ---- E. SED delegate -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "info, expected",
    [
        (make_license([("SED", None)]), True),  # legacy/new license carrying SED
        (make_license([("SED", PAST)]), False),  # expired
        (make_license([("SED", FUTURE)]), True),
        (None, False),
    ],
)
@pytest.mark.asyncio
async def test_system_sed_enabled_delegates(info, expected):
    m = Middleware()
    license_service(m, info)
    svc = create_service(m, SystemService)
    assert await svc.sed_enabled() is expected
