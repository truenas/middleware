import logging
from unittest.mock import Mock

import pytest
from truenas_pylicensed.features import LicenseFeature

from middlewared.api.current import KMIPEntry
from middlewared.plugins.kmip import KMIPLicenseDelegate, sed_keys, zfs_keys
from middlewared.plugins.kmip.keystore import KMIPKeyStore
from middlewared.pytest.unit.entitlements import facts_for_column, install_entitlements
from middlewared.pytest.unit.middleware import FakeJob, Middleware
from middlewared.service import CallError
from middlewared.service.context import ServiceContext


def _context(monkeypatch, *, column="HW+K", datasets=(), disks=()):
    m = Middleware()
    m.call_hook_sync = Mock()
    m.services.kmip.config = lambda: KMIPEntry(
        id=1,
        enabled=True,
        server="kmip.example.com",
        port=5696,
        certificate=1,
        certificate_authority=2,
        manage_sed_disks=True,
        manage_zfs_keys=True,
        ssl_version="PROTOCOL_TLSv1_2",
    )
    facts = facts_for_column(LicenseFeature.KMIP, column)
    install_entitlements(m, facts)
    tables = {"storage.encrypteddataset": list(datasets), "storage.disk": list(disks)}
    m["datastore.query"] = lambda table, filters=None, options=None: tables[table]
    m["datastore.config"] = lambda table, options=None: {"id": 1, "kmip_uid": None, "sed_passwd": ""}
    for module in (zfs_keys, sed_keys):
        monkeypatch.setattr(module, "test_connection", lambda *args: True)
    return ServiceContext(m, logging.getLogger("test"))


@pytest.mark.parametrize(
    "module,sync,pending_row",
    [
        (
            zfs_keys,
            lambda ctx: zfs_keys.sync_zfs_keys(ctx, KMIPKeyStore(), None, None),
            {"datasets": [{"id": 1, "name": "tank/a", "encryption_key": None, "kmip_uid": "uid-a"}]},
        ),
        (
            sed_keys,
            lambda ctx: sed_keys.sync_sed_keys(ctx, KMIPKeyStore(), None),
            {"disks": [{"identifier": "{serial}A", "passwd": "", "kmip_uid": "uid-a"}]},
        ),
    ],
)
@pytest.mark.parametrize(
    "column,rows,direction",
    [
        ("HW+K", True, "push"),
        ("CE+L", True, "pull"),
        ("CE+L", False, None),
    ],
)
def test_kmip_sync_direction(monkeypatch, module, sync, pending_row, column, rows, direction):
    """Unentitled keys come back; "nothing pending" is not "unreachable"."""
    called = []
    prefix = "zfs" if module is zfs_keys else "sed"
    for name in ("push", "pull"):
        monkeypatch.setattr(module, f"{name}_{prefix}_keys", lambda *args, name=name: called.append(name) or [])
    ctx = _context(monkeypatch, column=column, **(pending_row if rows else {}))

    assert sync(ctx) == []
    assert called == ([direction] if direction else [])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "zfs,sed,error",
    [
        (None, [], "kmip.sync_zfs_keys: KMIP server unreachable"),
        ([], ["Global SED Key"], "kmip.sync_sed_keys: Global SED Key"),
        ([], [], None),
    ],
)
async def test_kmip_delegate_fails_unless_both_syncs_finish(zfs, sed, error):
    """An unreachable server must not read as a completed revoke, and the revoke never force-clears escrow."""
    m = Middleware()
    called = []
    for name, result in (("kmip.sync_zfs_keys", zfs), ("kmip.sync_sed_keys", sed)):
        m[name] = lambda name=name, result=result: called.append(name) or FakeJob(result)
    delegate = KMIPLicenseDelegate(m)

    if error:
        with pytest.raises(CallError, match=error):
            await delegate.apply({LicenseFeature.KMIP: False})
    else:
        await delegate.apply({LicenseFeature.KMIP: False})
    assert called == ["kmip.sync_zfs_keys", "kmip.sync_sed_keys"]


@pytest.mark.asyncio
async def test_kmip_delegate_zfs_failure_still_syncs_sed():
    m = Middleware()
    called = []
    m["kmip.sync_zfs_keys"] = lambda: called.append("kmip.sync_zfs_keys") or FakeJob(error="boom")
    m["kmip.sync_sed_keys"] = lambda: called.append("kmip.sync_sed_keys") or FakeJob(["Global SED Key"])

    with pytest.raises(CallError, match="kmip.sync_zfs_keys: boom; kmip.sync_sed_keys: Global SED Key"):
        await KMIPLicenseDelegate(m).apply({LicenseFeature.KMIP: False})
    assert called == ["kmip.sync_zfs_keys", "kmip.sync_sed_keys"]
