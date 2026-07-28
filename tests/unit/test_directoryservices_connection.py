"""
Unit tests for DomainConnection standby local-SID reconciliation.

secrets.restore replays the local server SID that was current when the backup was taken,
which can lag the database value. _reconcile_standby_local_sid rewrites it from the
authoritative configuration before winbindd starts so the standby never comes up with a
stale local SAM domain SID (which cannot self-heal via a winbindd restart and only surfaces
after the standby is promoted).
"""

import logging

from unittest.mock import MagicMock

from middlewared.plugins.directoryservices_.connection import DomainConnection


def _connection_service():
    svc = object.__new__(DomainConnection)
    svc.middleware = MagicMock()
    svc.logger = logging.getLogger("test_directoryservices_connection")
    return svc


def test__reconcile_standby_local_sid_rewrites_when_sid_configured():
    """
    With a configured server SID, the standby must call smb.set_system_sid so the restored
    secrets.tdb is reconciled to the authoritative value before winbindd starts.
    """
    svc = _connection_service()

    def call_sync(method, *args, **kwargs):
        if method == "datastore.config":
            assert args[0] == "services.cifs"
            return {"cifs_SID": "S-1-5-21-1111111111-2222222222-3333333333"}
        if method == "smb.set_system_sid":
            return None
        raise AssertionError(f"unexpected middleware call: {method}")

    svc.middleware.call_sync.side_effect = call_sync

    svc._reconcile_standby_local_sid()

    assert any(c.args[0] == "smb.set_system_sid" for c in svc.middleware.call_sync.call_args_list), (
        "reconcile must invoke smb.set_system_sid when a server SID is configured"
    )


def test__reconcile_standby_local_sid_skips_when_sid_absent():
    """
    Without a stored SID, smb.local_server_sid() would synthesize a fresh random SID per
    call on the standby, so reconcile must skip rather than stamp a bogus SID onto the
    standby's secrets.tdb.
    """
    svc = _connection_service()

    def call_sync(method, *args, **kwargs):
        if method == "datastore.config":
            return {"cifs_SID": ""}
        if method == "smb.set_system_sid":
            raise AssertionError("smb.set_system_sid must not be called when no SID is configured")
        raise AssertionError(f"unexpected middleware call: {method}")

    svc.middleware.call_sync.side_effect = call_sync

    # Should return without raising and without calling smb.set_system_sid.
    svc._reconcile_standby_local_sid()


def test__reconcile_standby_local_sid_swallows_failures():
    """
    The reconcile is a best-effort pre-failover optimization. If smb.set_system_sid raises
    (e.g. `net setlocalsid` exits non-zero, or the winbindd restart job fails), the exception
    must NOT propagate -- otherwise it aborts activate_standby before the activation and
    health-recovery steps that follow it, leaving directory services inactive on the standby.
    """
    from middlewared.service_exception import CallError

    svc = _connection_service()

    def call_sync(method, *args, **kwargs):
        if method == "datastore.config":
            return {"cifs_SID": "S-1-5-21-1111111111-2222222222-3333333333"}
        if method == "smb.set_system_sid":
            raise CallError("setlocalsid failed: boom")
        raise AssertionError(f"unexpected middleware call: {method}")

    svc.middleware.call_sync.side_effect = call_sync

    # Must not raise: the failure is logged and swallowed.
    svc._reconcile_standby_local_sid()

    assert any(c.args[0] == "smb.set_system_sid" for c in svc.middleware.call_sync.call_args_list), (
        "reconcile should have attempted smb.set_system_sid before swallowing the failure"
    )
