"""KMIP's entitlement gate: the enable transition, and nothing else.

`do_update` runs its whole validation half before `verrors.check()` and only mutates anything
after it. That is what makes this testable without standing up the fifteen collaborators the
second half needs: `validate_port` is monkeypatched to always report an error, so the check
is a wall the call can never get past, and every assertion is about the errors raised at it.
"""

import pytest
from truenas_pylicensed.features import LicenseFeature

from middlewared.plugins.kmip.update import KMIPService
from middlewared.pytest.unit.entitlements import install_entitlements_for_column
from middlewared.pytest.unit.helpers import create_service
from middlewared.pytest.unit.middleware import FakeJob, Middleware
from middlewared.service import ValidationErrors

PORT_ATTRIBUTE = "kmip_update.port"
ENABLED_ATTRIBUTE = "kmip_update.enabled"

# The columns KMIP's vector (0,0,0,1,0,1) grants: a key on either hardware side.
GRANTING_COLUMNS = ("HW+K", "CE+K")
ALL_COLUMNS = ("CE", "HW", "HW+L", "HW+K", "CE+L", "CE+K")


def _config(enabled):
    return {
        "id": 1,
        "enabled": enabled,
        "server": "kmip.example.com",
        "port": 5696,
        "certificate": 1,
        "certificate_authority": 2,
        "manage_sed_disks": False,
        "manage_zfs_keys": False,
        "ssl_version": "PROTOCOL_TLSv1_2",
    }


def _service(monkeypatch, middleware, *, enabled):
    async def poisoned_validate_port(*args, **kwargs):
        verrors = ValidationErrors()
        verrors.add(PORT_ATTRIBUTE, "Refusing to reach the mutation half of do_update.")
        return verrors

    monkeypatch.setattr("middlewared.plugins.kmip.update.validate_port", poisoned_validate_port)

    middleware["certificate.cert_services_validation"] = lambda *args: ValidationErrors()
    middleware["certificate.query"] = lambda *args: [{"id": 2, "certificate": "ca"}]
    middleware["kmip.kmip_sync_pending"] = lambda *args: False

    async def config():
        return _config(enabled)

    service = create_service(middleware, KMIPService)
    service.config = config
    return service


async def _attributes(service, data):
    with pytest.raises(ValidationErrors) as exc:
        await service.do_update(FakeJob(), data)
    return [error.attribute for error in exc.value.errors]


@pytest.mark.asyncio
@pytest.mark.parametrize("column", ALL_COLUMNS)
async def test_kmip_enable_transition_is_gated(monkeypatch, column):
    m = Middleware()
    checked = install_entitlements_for_column(m, LicenseFeature.KMIP, column)
    service = _service(monkeypatch, m, enabled=False)

    attributes = await _attributes(service, {"enabled": True, "server": "kmip.example.com"})

    assert checked == [LicenseFeature.KMIP]
    # The poisoned port error is always there, so its absence would mean the wall moved and
    # everything below it is no longer reachable by this test.
    assert PORT_ATTRIBUTE in attributes
    assert (ENABLED_ATTRIBUTE in attributes) is (column not in GRANTING_COLUMNS)


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [True, False])
async def test_kmip_does_not_consult_the_entitlement_unless_enabling(monkeypatch, enabled):
    # Disabling KMIP is how escrowed ZFS and SED keys are pulled back to the local database.
    # A system that lost the entitlement has to keep that route, or its keys are stranded, so
    # the check must not be reached at all when KMIP is already on.
    m = Middleware()
    checked = install_entitlements_for_column(m, LicenseFeature.KMIP, "CE")
    service = _service(monkeypatch, m, enabled=True)

    attributes = await _attributes(service, {"enabled": enabled, "server": "kmip.example.com"})

    assert checked == []
    assert PORT_ATTRIBUTE in attributes
    assert ENABLED_ATTRIBUTE not in attributes
