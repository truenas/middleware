"""KMIP's entitlement gate: the enable transition, and nothing else.

`do_update` runs its whole validation half before `verrors.check()` and only mutates anything
after it. That is what makes this testable without standing up the collaborators the mutation
half needs: `validate_port` is monkeypatched to always report an error, so the check is a wall
the call can never get past, and every assertion is about the errors raised at it.
"""

import logging

import pytest
from truenas_pylicensed.features import LicenseFeature

from middlewared.api.current import KMIPEntry, KMIPUpdate
from middlewared.plugins.kmip.config import KMIPConfigServicePart
from middlewared.pytest.unit.entitlements import install_entitlements_for_column
from middlewared.pytest.unit.middleware import FakeJob, Middleware
from middlewared.service import ValidationErrors
from middlewared.service.context import ServiceContext

PORT_ATTRIBUTE = "kmip_update.port"
ENABLED_ATTRIBUTE = "kmip_update.enabled"

# KMIP grants on a key and nowhere else, so one granting column and one denying one is the
# whole of the gate.
GATE_COLUMNS = [("HW+K", True), ("CE+L", False)]


def _entry(enabled):
    return KMIPEntry(
        id=1,
        enabled=enabled,
        server="kmip.example.com",
        port=5696,
        certificate=1,
        certificate_authority=2,
        manage_sed_disks=False,
        manage_zfs_keys=False,
        ssl_version="PROTOCOL_TLSv1_2",
    )


def _svc_part(monkeypatch, middleware, *, enabled):
    async def poisoned_validate_port(*args, **kwargs):
        verrors = ValidationErrors()
        verrors.add(PORT_ATTRIBUTE, "Refusing to reach the mutation half of do_update.")
        return verrors

    monkeypatch.setattr("middlewared.plugins.kmip.config.validate_port", poisoned_validate_port)

    # Both of these are read for their value, not called for effect: an auto-Mock
    # `cert_services_validation` blows up `verrors.extend`, and an auto-Mock `kmip_sync_pending`
    # is truthy, which injects SYNC_ERROR at the very attribute these tests assert on.
    middleware.services.certificate.cert_services_validation = lambda *args: ValidationErrors()
    middleware.services.certificate.query = lambda *args: []
    middleware.services.kmip.kmip_sync_pending = lambda *args: False

    svc_part = KMIPConfigServicePart(ServiceContext(middleware, logging.getLogger("test")))

    async def config():
        return _entry(enabled)

    svc_part.config = config
    return svc_part


async def _attributes(svc_part, **update):
    with pytest.raises(ValidationErrors) as exc:
        await svc_part.do_update(FakeJob(), KMIPUpdate(**update))
    return [error.attribute for error in exc.value.errors]


@pytest.mark.asyncio
@pytest.mark.parametrize("column,entitled", GATE_COLUMNS)
async def test_kmip_enable_transition_is_gated(monkeypatch, column, entitled):
    m = Middleware()
    checked = install_entitlements_for_column(m, LicenseFeature.KMIP, column)
    svc_part = _svc_part(monkeypatch, m, enabled=False)

    attributes = await _attributes(svc_part, enabled=True, server="kmip.example.com")

    assert checked == [LicenseFeature.KMIP]
    # The poisoned port error is always there, so its absence would mean the wall moved and
    # everything below it is no longer reachable by this test.
    assert PORT_ATTRIBUTE in attributes
    assert (ENABLED_ATTRIBUTE in attributes) is not entitled


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [True, False])
async def test_kmip_does_not_consult_the_entitlement_unless_enabling(monkeypatch, enabled):
    # Disabling KMIP is how escrowed ZFS and SED keys are pulled back to the local database.
    # A system that lost the entitlement has to keep that route, or its keys are stranded, so
    # the check must not be reached at all when KMIP is already on.
    m = Middleware()
    checked = install_entitlements_for_column(m, LicenseFeature.KMIP, "CE")
    svc_part = _svc_part(monkeypatch, m, enabled=True)

    attributes = await _attributes(svc_part, enabled=enabled, server="kmip.example.com")

    assert checked == []
    assert PORT_ATTRIBUTE in attributes
    assert ENABLED_ATTRIBUTE not in attributes
