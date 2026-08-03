"""
Unit tests for SMBService.set_system_sid winbindd-restart decision.

set_system_sid writes the configured local server SID with ``net setlocalsid`` and, when it
changes the SID under a running winbindd, restarts winbindd so its view of the local SAM
domain is rebuilt (otherwise group-token expansion fails with NT_STATUS_NO_SUCH_DOMAIN). The
subtlety these tests lock in: a failure to *read* the current SID must not be mistaken for a
genuinely-absent prior SID -- in the read-failure case we cannot prove the SID was unchanged,
so winbindd must still be restarted.
"""

import logging

from unittest.mock import MagicMock, patch

import pytest

from middlewared.plugins.smb_ import sid as sid_module
from middlewared.plugins.smb_.sid import SMBService
from middlewared.service_exception import MatchNotFound


NETBIOS = "TRUENAS"
SERVER_SID = "S-1-5-21-1111111111-2222222222-3333333333"
OLD_SID = "S-1-5-21-9999999999-8888888888-7777777777"


def _smb_service(current_sid, *, idmap_started=True, sid_exc=None):
    """
    Build an SMBService instance wired with mocks. ``current_sid`` is what
    directoryservices.secrets.domain_sid returns; ``sid_exc``, if set, is raised by that
    call instead (to exercise the absent / read-failure branches). The stored cifs_SID is
    always SERVER_SID, so local_server_sid() returns SERVER_SID without needing failover.
    """
    svc = object.__new__(SMBService)
    svc.middleware = MagicMock()
    svc.logger = logging.getLogger("test_smb_set_system_sid")

    restart_job = MagicMock()

    def call_sync(name, *args, **kwargs):
        if name == "datastore.config":
            return {"cifs_SID": SERVER_SID}
        if name == "smb.config":
            return {"netbiosname": NETBIOS}
        if name == "directoryservices.secrets.domain_sid":
            if sid_exc is not None:
                raise sid_exc
            return current_sid
        if name == "service.started":
            return idmap_started
        if name == "service.control":
            return restart_job
        raise AssertionError(f"unexpected middleware call: {name}")

    svc.middleware.call_sync.side_effect = call_sync
    svc._restart_job = restart_job
    return svc


def _restarted(svc):
    """True if a winbindd (idmap) RESTART was issued."""
    return any(
        c.args[0] == "service.control" and c.args[1] == "RESTART" and c.args[2] == "idmap"
        for c in svc.middleware.call_sync.call_args_list
    )


@pytest.fixture
def net_setlocalsid_ok():
    with patch.object(sid_module.subprocess, "run") as run:
        run.return_value = MagicMock(returncode=0, stderr=b"")
        yield run


def test_read_failure_restarts_winbindd(net_setlocalsid_ok):
    """
    A transient/unexpected failure to read the current SID must not be treated as
    'no prior SID'. We can't prove the SID is unchanged and we just ran setlocalsid, so
    winbindd must be restarted -- otherwise it is left on a possibly-stale local SAM SID,
    reintroducing the NT_STATUS_NO_SUCH_DOMAIN denial this whole method exists to prevent.
    """
    svc = _smb_service(current_sid=None, idmap_started=True, sid_exc=RuntimeError("tdb locked"))

    svc.set_system_sid()

    assert net_setlocalsid_ok.called
    assert _restarted(svc), "read failure with winbindd running must trigger a restart"
    svc._restart_job.wait_sync.assert_called_once_with(raise_error=True)


def test_absent_prior_sid_does_not_restart(net_setlocalsid_ok):
    """
    A genuinely absent prior SID (fresh secrets.tdb -- MatchNotFound) means winbindd has
    nothing stale to rebuild, so setlocalsid runs but no restart is issued.
    """
    svc = _smb_service(current_sid=None, idmap_started=True, sid_exc=MatchNotFound())

    svc.set_system_sid()

    assert net_setlocalsid_ok.called
    assert not _restarted(svc), "absent prior SID must not trigger a winbindd restart"


def test_missing_secrets_file_does_not_restart(net_setlocalsid_ok):
    """A missing secrets.tdb (FileNotFoundError) is likewise a genuine absence, not a change."""
    svc = _smb_service(current_sid=None, idmap_started=True, sid_exc=FileNotFoundError())

    svc.set_system_sid()

    assert net_setlocalsid_ok.called
    assert not _restarted(svc)


def test_changed_sid_restarts_winbindd(net_setlocalsid_ok):
    """A real change of the local SID under a running winbindd triggers a restart."""
    svc = _smb_service(current_sid=OLD_SID, idmap_started=True)

    svc.set_system_sid()

    assert net_setlocalsid_ok.called
    assert _restarted(svc)
    svc._restart_job.wait_sync.assert_called_once_with(raise_error=True)


def test_unchanged_sid_is_a_noop(net_setlocalsid_ok):
    """When the stored SID already matches, neither setlocalsid nor a restart runs."""
    svc = _smb_service(current_sid=SERVER_SID, idmap_started=True)

    svc.set_system_sid()

    assert not net_setlocalsid_ok.called
    assert not _restarted(svc)


def test_read_failure_no_restart_when_winbindd_stopped(net_setlocalsid_ok):
    """
    Even on a read failure, if winbindd isn't running there is no live view to rebuild, so
    no restart is attempted (the SID is written for the next start to pick up).
    """
    svc = _smb_service(current_sid=None, idmap_started=False, sid_exc=RuntimeError("tdb locked"))

    svc.set_system_sid()

    assert net_setlocalsid_ok.called
    assert not _restarted(svc)
