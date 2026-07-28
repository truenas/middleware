"""
Unit tests for the DomainSecrets backup pruning behaviour. Without pruning, every
hostname change leaves an orphan {OLDHOST$} key in cifs.secrets containing a full
dump of the prior bind's secrets. The fix makes backup() retain only the current
{NETBIOSNAME$} key.
"""

import asyncio
import json
import logging
import os
import struct
import subprocess
from base64 import b64encode

import pytest
import tdb

from unittest.mock import AsyncMock, MagicMock

from middlewared.plugins.directoryservices_ import secrets as secrets_mod
from middlewared.plugins.directoryservices_.secrets import DomainSecrets
from middlewared.service_exception import CallError
from middlewared.utils.tdb import TDBDataType, get_tdb_handle, keys_are_null_terminated


@pytest.fixture
def secrets_tdb(secrets_service, tmp_path, monkeypatch):
    """
    Point the secrets service at a real, empty secrets.tdb in a temp dir and run in
    non-clustered mode. The tdb is opened O_RDWR without O_CREAT, so it must exist first.
    """
    tdb_path = str(tmp_path / 'secrets.tdb')
    tdb.Tdb(tdb_path, 0, tdb.DEFAULT, os.O_CREAT | os.O_RDWR, 0o600).close()
    monkeypatch.setattr(
        secrets_mod, 'SECRETS_TDB_CONFIG', (tdb_path, secrets_mod.SECRETS_TDB_OPTIONS)
    )
    secrets_service.middleware.call_sync = MagicMock(return_value={'stateful_failover': False})
    return secrets_service


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

    asyncio.run(secrets_service.backup())

    # The datastore.update call should contain only the current netbiosname's entry.
    saved = json.loads(captured["args"][2]["secrets"])
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
    asyncio.run(secrets_service.backup())


def test__backup_refuses_overwrite_when_machine_secret_absent(secrets_service):
    """
    A secrets.tdb dump that lacks a machine account password must NOT overwrite the stored
    backup -- otherwise a transiently incomplete secrets.tdb (local SID written, machine
    secret not yet restored) could replace a good backup with a machine-secret-less one.
    """
    fresh_dump = {
        # Local SID only -- no SECRETS/MACHINE_PASSWORD/* entry.
        "SECRETS/SID/NEWHOST": "c2lkYnl0ZXM=",
    }
    called = {"datastore_update": False}

    async def fake_call(method, *args, **kwargs):
        if method == "failover.status":
            return "SINGLE"
        if method == "smb.config":
            return {"netbiosname": "NEWHOST"}
        if method == "directoryservices.secrets.dump":
            return fresh_dump
        if method == "datastore.update":
            called["datastore_update"] = True
            return None
        raise AssertionError(f"unexpected middleware call: {method}")

    async def fake_get_db_secrets():
        return {"id": 1, "NEWHOST$": {"SECRETS/MACHINE_PASSWORD/NEWDOMAIN": "Z29vZA=="}}

    secrets_service.get_db_secrets = fake_get_db_secrets
    secrets_service.middleware.call.side_effect = fake_call

    asyncio.run(secrets_service.backup())

    assert called["datastore_update"] is False, (
        "backup() must not overwrite the stored secrets when the current secrets.tdb has no "
        "machine account password -- doing so destroys the good backup."
    )


def test__backup_allows_missing_machine_secret_when_explicit(secrets_service):
    """
    The domain-leave path deliberately backs up a nuked secrets.tdb to clear the stored
    secret. allow_missing_machine_secret=True must permit that overwrite.
    """
    fresh_dump = {"SECRETS/SID/NEWHOST": "c2lkYnl0ZXM="}
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
            return None
        raise AssertionError(f"unexpected middleware call: {method}")

    async def fake_get_db_secrets():
        return {"id": 1, "NEWHOST$": {"SECRETS/MACHINE_PASSWORD/NEWDOMAIN": "Z29vZA=="}}

    secrets_service.get_db_secrets = fake_get_db_secrets
    secrets_service.middleware.call.side_effect = fake_call

    asyncio.run(secrets_service.backup(allow_missing_machine_secret=True))

    saved = json.loads(captured["args"][2]["secrets"])
    assert saved == {"NEWHOST$": fresh_dump}, (
        "With allow_missing_machine_secret=True the clearing backup must proceed and store "
        "the (machine-secret-less) dump."
    )


def test__last_password_change_real_tdb_roundtrip(secrets_service, tmp_path, monkeypatch):
    """
    Regression for the stray ']' in the secrets.tdb key, exercised end-to-end against a real
    secrets.tdb instead of a stubbed fetch. last_password_change must read
    SECRETS/MACHINE_LAST_CHANGE_TIME/<DOMAIN> -- the exact key the writer and the DB-side
    reader (directoryservices.get_last_password_change) use. With the ']' the lookup misses,
    the disk read raises MatchNotFound, last_password_change returns None, and
    kerberos.check_updated_keytab churns a backup + keytab rewrite every hour.

    Writing a real entry and reading it back through samba's tdb library covers the full
    key + struct + base64 path that the stray bracket broke -- a wrong key surfaces here as a
    failure rather than passing because the fetch itself was mocked away.
    """
    tdb_path = str(tmp_path / 'secrets.tdb')
    # The secrets.tdb path opens O_RDWR without O_CREAT, so the db must already exist.
    tdb.Tdb(tdb_path, 0, tdb.DEFAULT, os.O_CREAT | os.O_RDWR, 0o600).close()
    monkeypatch.setattr(
        secrets_mod, 'SECRETS_TDB_CONFIG', (tdb_path, secrets_mod.SECRETS_TDB_OPTIONS)
    )

    key = f'{secrets_mod.Secrets.MACHINE_LAST_CHANGE_TIME.value}/MSC'
    with get_tdb_handle(tdb_path, secrets_mod.SECRETS_TDB_OPTIONS) as hdl:
        hdl.store(key, b64encode(struct.pack('<L', 1718800000)).decode())

    secrets_service.middleware.call_sync = MagicMock(return_value={'stateful_failover': False})

    assert secrets_service.last_password_change('msc') == 1718800000


def test__get_db_secrets_invalid_json_returns_id_only(secrets_service):
    """
    Corrupt JSON in cifs.secrets must degrade to "no backup" ({'id': ...}) instead of
    raising UnboundLocalError -- previously the except branch fell through to
    `return {'id': ...} | secrets` with `secrets` never bound.
    """
    async def fake_call(method, *args, **kwargs):
        assert method == "datastore.config"
        return {"id": 5, "secrets": "{not valid json"}

    secrets_service.middleware.call.side_effect = fake_call

    assert asyncio.run(secrets_service.get_db_secrets()) == {"id": 5}


def test__get_db_secrets_valid_json_merges_id(secrets_service):
    """A well-formed backup blob is returned merged with the row id."""
    blob = {"NEWHOST$": {"SECRETS/MACHINE_PASSWORD/NEWDOMAIN": "ZnJlc2g="}}

    async def fake_call(method, *args, **kwargs):
        assert method == "datastore.config"
        return {"id": 7, "secrets": json.dumps(blob)}

    secrets_service.middleware.call.side_effect = fake_call

    assert asyncio.run(secrets_service.get_db_secrets()) == {"id": 7} | blob


def test__set_ipa_secret_pipes_raw_password_and_stamps_version(secrets_tdb, monkeypatch):
    """
    The IPA <> SMB auth bug: the machine-account password handed to `net changesecretpw`
    must be the raw bytes that the SMB keytab was derived from -- base64/otherwise encoding
    it desynchronises secrets.tdb from the keytab and breaks SMB machine authentication.
    set_ipa_secret must also stamp the credential-format version so systems joined by the
    broken build can be detected and healed after an upgrade.
    """
    captured = {}

    def fake_run(cmd, *args, **kwargs):
        captured['cmd'] = cmd
        captured['input'] = kwargs.get('input')
        return subprocess.CompletedProcess(cmd, 0, stdout=b'', stderr=b'')

    monkeypatch.setattr(secrets_mod.subprocess, 'run', fake_run)

    # Deliberately include characters outside the base64 alphabet to catch any re-encoding.
    raw_password = b'S0me-R@w_Machine!:;<=>()[]~Pass'
    secrets_tdb.set_ipa_secret('MYDOMAIN', raw_password)

    assert captured['cmd'][:2] == ['net', 'changesecretpw']
    assert captured['input'] == raw_password, 'password must be piped to net changesecretpw verbatim'

    # A successful write records the current credential-format version for the domain.
    assert secrets_tdb.ipa_cred_version('MYDOMAIN') == secrets_mod.IPA_SMB_CRED_VERSION


def test__set_ipa_secret_error_reports_stderr(secrets_tdb, monkeypatch):
    """
    On failure the raised error must surface `net changesecretpw`'s diagnostics, which it
    writes to stderr -- reporting stdout (empty on the failure path) left the error blank.
    """
    def fake_run(cmd, *args, **kwargs):
        return subprocess.CompletedProcess(
            cmd, 1, stdout=b'', stderr=b'net: unable to write machine account password'
        )

    monkeypatch.setattr(secrets_mod.subprocess, 'run', fake_run)

    with pytest.raises(CallError, match='unable to write machine account password'):
        secrets_tdb.set_ipa_secret('MYDOMAIN', b'whatever')


def test__ipa_cred_version_absent_reads_as_zero(secrets_tdb):
    """
    A domain with no recorded credential version -- i.e. one joined before version tracking
    existed -- must read as 0 so the health check knows to regenerate its SMB credential.
    """
    assert secrets_tdb.ipa_cred_version('OLDDOMAIN') == 0


@pytest.mark.parametrize('name,data_type,expected', [
    # secrets.tdb is the odd one out: samba keys it via string_tdb_data() (strlen, no
    # terminator), so its keys MUST NOT be null-terminated. The value returned here is
    # consumed identically by the local TDBHandle and the clustered CTDBHandle; when the
    # two disagreed (CTDBHandle hardcoded True) winbindd could not fetch the domain SID
    # and SMB stateful failover broke ("Could not fetch our SID - did we join?").
    ('secrets.tdb', TDBDataType.BYTES, False),
    ('/var/lib/truenas-samba/private/secrets.tdb', TDBDataType.BYTES, False),
    # Most samba databases key via string_term_tdb_data() (strlen + 1).
    ('gencache.tdb', TDBDataType.BYTES, True),
    ('group_mapping.tdb', TDBDataType.BYTES, True),
    ('group_mapping_rejects.tdb', TDBDataType.BYTES, True),
    ('passdb.tdb', TDBDataType.BYTES, True),
    ('share_info.tdb', TDBDataType.BYTES, True),       # default: BYTES -> terminated
    ('winbindd_cache.tdb', TDBDataType.BYTES, True),   # default: BYTES -> terminated
    ('middleware_cache', TDBDataType.JSON, False),     # middleware-owned JSON -> not
])
def test__keys_are_null_terminated_conventions(name, data_type, expected):
    """
    Lock the per-database key convention that both TDB access paths share. A regression
    that flips secrets.tdb back to null-terminated re-breaks winbindd on stateful failover.
    """
    assert keys_are_null_terminated(name, data_type) is expected


def test__secrets_tdb_keys_are_not_null_terminated_on_disk(tmp_path):
    """
    End-to-end proof that a key written through the secrets.tdb handle lands on disk
    without a trailing NUL -- the exact byte layout samba's secrets_fetch() expects. If
    the handle null-terminates the key, secrets_fetch_domain_sid() misses and winbindd
    aborts. Inspecting the raw underlying tdb keys (bypassing the wrapper, which would
    hide the terminator) surfaces a regression as a failure here.
    """
    tdb_path = str(tmp_path / 'secrets.tdb')
    # secrets.tdb opens O_RDWR without O_CREAT, so the db must already exist.
    tdb.Tdb(tdb_path, 0, tdb.DEFAULT, os.O_CREAT | os.O_RDWR, 0o600).close()

    key = 'SECRETS/SID/ACME'
    with get_tdb_handle(tdb_path, secrets_mod.SECRETS_TDB_OPTIONS) as hdl:
        hdl.store(key, b64encode(b'\x01\x04rawsidbytes').decode())
        raw_keys = list(hdl.hdl.keys())  # underlying tdb.Tdb -> raw key bytes

    assert key.encode() in raw_keys, f'expected un-terminated key on disk; got {raw_keys}'
    assert key.encode() + b'\x00' not in raw_keys, 'secrets key must not be NUL-terminated'
