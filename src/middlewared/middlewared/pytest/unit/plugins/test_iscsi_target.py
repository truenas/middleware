import pytest
from truenas_pylicensed.features import LicenseFeature

from middlewared.plugins.iscsi_.targets import iSCSITargetService
from middlewared.pytest.unit.entitlements import install_entitlements_for_column
from middlewared.pytest.unit.helpers import create_service
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service import ValidationErrors


def target_middleware(column):
    m = Middleware()
    m["iscsi.target.query"] = lambda *args: []
    m["datastore.query"] = lambda *args: []

    checked = install_entitlements_for_column(m, LicenseFeature.FIBRECHANNEL, column)
    return m, checked


async def validate(m, mode):
    verrors = ValidationErrors()
    svc = create_service(m, iSCSITargetService)
    await svc._iSCSITargetService__validate(
        verrors,
        {"name": "target1", "alias": None, "mode": mode, "groups": [], "auth_networks": []},
        "iscsi_target_create",
    )
    return verrors


@pytest.mark.parametrize("mode", ["FC", "BOTH"])
@pytest.mark.asyncio
async def test_target_mode_rejected_when_not_entitled(mode):
    m, checked = target_middleware("CE+L")

    verrors = await validate(m, mode)

    assert checked == [LicenseFeature.FIBRECHANNEL]
    assert [(e.attribute, e.errmsg) for e in verrors.errors] == [
        ("iscsi_target_create.mode", "Fibre Channel not enabled"),
    ]


@pytest.mark.asyncio
async def test_target_mode_allowed_when_entitled():
    # HW+L rather than a key column: Fibre Channel is granted by any license on appliance
    # hardware, without needing a key of its own.
    m, checked = target_middleware("HW+L")

    verrors = await validate(m, "FC")

    assert checked == [LicenseFeature.FIBRECHANNEL]
    assert verrors.errors == []


@pytest.mark.asyncio
async def test_iscsi_only_target_skips_entitlement_check():
    m, checked = target_middleware("CE")

    verrors = await validate(m, "ISCSI")

    assert checked == []
    assert verrors.errors == []
