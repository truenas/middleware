"""
Unit tests for the DomainSecrets backup pruning behaviour. Without pruning, every
hostname change leaves an orphan {OLDHOST$} key in cifs.secrets containing a full
dump of the prior bind's secrets. The fix makes backup() retain only the current
{NETBIOSNAME$} key.
"""

import asyncio
import json
import logging

import pytest

from unittest.mock import AsyncMock, MagicMock

from middlewared.plugins.directoryservices_.secrets import DomainSecrets


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture
def secrets_service():
    """
    Build a DomainSecrets instance with a Mock middleware. Tests configure the
    AsyncMock side effects per scenario.
    """
    svc = object.__new__(DomainSecrets)
    svc.middleware = MagicMock()
    svc.middleware.call = AsyncMock()
    svc.logger = logging.getLogger("test_directoryservices_secrets")
    return svc


def test__backup_drops_stale_netbiosname_keys(secrets_service):
    """
    When secrets.backup() runs with cifs.secrets already containing entries for prior
    hostnames, only the current netbiosname's entry should remain in the saved payload.
    Old keys leak full secret dumps from the system's history and shouldn't accumulate.
    """
    # Existing DB row holds backups for two old hostnames AND the current one.
    db_secrets_existing = {
        "id": 1,
        "OLDHOST1$": {"SECRETS/MACHINE_PASSWORD/OLDDOMAIN1": "b3ZlcjE="},
        "OLDHOST2$": {"SECRETS/MACHINE_PASSWORD/OLDDOMAIN2": "b3ZlcjI="},
        "NEWHOST$": {"SECRETS/MACHINE_PASSWORD/NEWDOMAIN": "b2xkZHVtcA=="},
    }
    fresh_dump = {
        "SECRETS/MACHINE_PASSWORD/NEWDOMAIN": "ZnJlc2g=",
        "SECRETS/SID/NEWDOMAIN": "c2lkYnl0ZXM=",
    }

    captured = {}

    async def fake_call(method, *args, **kwargs):
        if method == "failover.status":
            return "SINGLE"
        if method == "smb.config":
            return {"netbiosname": "NEWHOST"}
        if method == "directoryservices.secrets.dump":
            return fresh_dump
        if method == "datastore.update":
            captured["args"] = args
            captured["kwargs"] = kwargs
            return None
        raise AssertionError(f"unexpected middleware call: {method}")

    # get_db_secrets is a method on the same Service; for this unit test we replace
    # it directly so we don't need to spin up the datastore.config path.
    async def fake_get_db_secrets():
        return dict(db_secrets_existing)

    secrets_service.get_db_secrets = fake_get_db_secrets
    secrets_service.middleware.call.side_effect = fake_call

    _run(secrets_service.backup())

    # The datastore.update call should contain only the current netbiosname's entry.
    saved = json.loads(captured["args"][3]["secrets"])
    assert set(saved.keys()) == {"NEWHOST$"}, (
        f"cifs.secrets after backup() should contain only the current NETBIOSNAME$ key; "
        f"got {sorted(saved.keys())}."
    )
    # And that entry should be the fresh dump, not the old one.
    assert saved["NEWHOST$"] == fresh_dump


def test__backup_skips_when_failover_status_is_backup(secrets_service):
    """
    On the standby controller secrets.backup() must short-circuit before touching the
    DB. Confirm pruning is skipped on standby (we don't want a standby with a stale
    view of what the active node thinks the secrets dump looks like to prune away the
    active's authoritative entry).
    """

    async def fake_call(method, *args, **kwargs):
        if method == "failover.status":
            return "BACKUP"
        # No other calls should happen on the BACKUP path.
        raise AssertionError(f"unexpected middleware call on BACKUP: {method}")

    secrets_service.middleware.call.side_effect = fake_call

    # Should return without raising and without making any non-failover.status calls.
    _run(secrets_service.backup())
