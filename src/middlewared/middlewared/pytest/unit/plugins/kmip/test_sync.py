import contextlib
import logging
from types import SimpleNamespace
from unittest.mock import Mock

from kmip.core import enums
from kmip.pie.exceptions import KmipOperationFailure
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


@pytest.mark.parametrize(
    "delete,uid_cleared",
    [
        ("destroyed", True),
        (KmipOperationFailure(enums.ResultStatus.OPERATION_FAILED, enums.ResultReason.ITEM_NOT_FOUND, "gone"), True),
        (KmipOperationFailure(enums.ResultStatus.OPERATION_FAILED, enums.ResultReason.PERMISSION_DENIED, "no"), False),
        (CallError("Failed to connect to KMIP Server"), False),
    ],
)
def test_kmip_pull_clears_uid_only_once_the_server_copy_is_gone(monkeypatch, delete, uid_cleared):
    """Clearing `kmip_uid` before the server delete orphans the escrowed copy for good."""
    row = {"id": 1, "name": "tank/a", "encryption_key": None, "kmip_uid": "uid-a"}
    ctx = _context(monkeypatch, column="CE+L", datasets=[row])
    ctx.middleware.services.zfs.resource.list_impl = lambda query: [{"name": "tank/a"}]
    monkeypatch.setattr(zfs_keys, "check_key", lambda *args, **kwargs: True)
    updates = []
    ctx.middleware["datastore.update"] = lambda table, id_, data: updates.append(data)

    def destroy(uid):
        if isinstance(delete, Exception):
            raise delete

    @contextlib.contextmanager
    def connection(*args):
        if isinstance(delete, CallError):
            raise delete
        yield SimpleNamespace(revoke=lambda *args: None, destroy=destroy)

    monkeypatch.setattr("middlewared.plugins.kmip.connection.connection_config", lambda *args: {})
    monkeypatch.setattr("middlewared.plugins.kmip.connection.kmip_connection", connection)
    store = KMIPKeyStore()
    store.zfs_keys["tank/a"] = "key-a"

    assert zfs_keys.sync_zfs_keys(ctx, store, None, None) == []
    expected = [{"encryption_key": "key-a"}] + ([{"kmip_uid": None}] if uid_cleared else [])
    assert updates == expected


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
