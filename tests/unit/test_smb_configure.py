"""
Unit tests for the winbindd restart in SMBService.configure.

smb.set_system_sid runs before smb.set_configured, when an idmap RESTART is a no-op, so
configure asks it to defer the restart and issues the restart itself after
smb.set_configured.
"""

import asyncio
import logging

from unittest.mock import AsyncMock, MagicMock

from middlewared.plugins.smb import SMBService
from middlewared.service_exception import CallError


RESTART_IDMAP = ("RESTART", "idmap", {"silent": False, "ha_propagate": False})


def _run_configure(winbindd_stale, restart_exc=None):
    svc = object.__new__(SMBService)
    svc.middleware = MagicMock()
    svc.logger = logging.getLogger("test_smb_configure")
    svc.netif_wait = AsyncMock()
    svc.reconcile_local_accounts = AsyncMock()

    restart_job = MagicMock()
    restart_job.wait = AsyncMock(side_effect=restart_exc)
    calls = []

    def call(name, *args):
        calls.append((name, args))
        if name == "smb.set_system_sid":
            return winbindd_stale
        if name == "service.control":
            return restart_job
        return None

    svc.middleware.call = AsyncMock(side_effect=call)
    config_job = MagicMock()
    asyncio.run(svc.configure(config_job))
    return calls, restart_job, config_job


def _names(calls):
    return [name for name, args in calls]


def test_stale_winbindd_restarted_after_set_configured():
    calls, restart_job, config_job = _run_configure(winbindd_stale=True)
    names = _names(calls)

    assert ("smb.set_system_sid", (False,)) in calls
    assert ("service.control", RESTART_IDMAP) in calls
    assert names.index("smb.set_configured") < names.index("service.control"), (
        "the restart must follow smb.set_configured, or IdmapService.restart skips it"
    )
    restart_job.wait.assert_awaited_once_with(raise_error=True)
    config_job.set_progress.assert_called_with(100, "Finished configuring SMB.")


def test_no_restart_when_winbindd_not_stale():
    calls, restart_job, config_job = _run_configure(winbindd_stale=False)

    assert "service.control" not in _names(calls)
    config_job.set_progress.assert_called_with(100, "Finished configuring SMB.")


def test_restart_failure_does_not_fail_configure():
    calls, restart_job, config_job = _run_configure(winbindd_stale=True, restart_exc=CallError("winbind failed"))

    restart_job.wait.assert_awaited_once_with(raise_error=True)
    config_job.set_progress.assert_called_with(100, "Finished configuring SMB.")
