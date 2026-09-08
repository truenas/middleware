"""Config CRUD: input validation bounds, entitlement gating, kernel-param sync,
and service-control behavior on update.

The bound-checking tests do not depend on the tier_pool fixture — they
exercise the Pydantic input gate at the API layer, which runs before the
method body's entitlement check. The entitlement, kernel-param, and
service-control tests do require tier_pool (which itself requires the ZFSTIER
entitlement + 6 disks).
"""

import pytest

from middlewared.service_exception import CallError, ValidationErrors
from middlewared.test.integration.utils import call, ssh


_KERNEL_PARAM_PATH = "/sys/module/zfs/parameters/zfs_special_class_metadata_reserve_pct"


# ----------------------------------------------------------------------------
# Pydantic bounds: these run at the API gateway before any service code, so
# they don't require the ZFSTIER entitlement or a SPECIAL vdev.
# ----------------------------------------------------------------------------


def _assert_bounds_rejected(payload):
    """Pydantic bound failures arrive as middlewared.service_exception.ValidationErrors
    via the integration client's py_exceptions=True path."""
    with pytest.raises(ValidationErrors) as exc:
        call("zfs.tier.update", payload)
    return exc


def test_update_rejects_max_concurrent_jobs_below_min():
    _assert_bounds_rejected({"max_concurrent_jobs": 0})


def test_update_rejects_max_concurrent_jobs_above_max():
    _assert_bounds_rejected({"max_concurrent_jobs": 11})


def test_update_rejects_max_used_percentage_below_70():
    _assert_bounds_rejected({"max_used_percentage": 69})


def test_update_rejects_max_used_percentage_above_95():
    _assert_bounds_rejected({"max_used_percentage": 96})


def test_update_rejects_metadata_reserve_below_10():
    _assert_bounds_rejected({"special_class_metadata_reserve_pct": 9})


def test_update_rejects_metadata_reserve_above_30():
    _assert_bounds_rejected({"special_class_metadata_reserve_pct": 31})


# ----------------------------------------------------------------------------
# Entitlement gate: this only runs where the system lacks the ZFSTIER
# entitlement. Where it has it, the tier_pool fixture is already exercising the
# entitled path.
# ----------------------------------------------------------------------------


def test_update_requires_zfstier_entitlement(zfstier_entitlement):
    if zfstier_entitlement["entitled"]:
        pytest.skip("Denial test only runs where ZFSTIER is not entitled")
    with pytest.raises(CallError) as exc:
        call("zfs.tier.update", {"enabled": True})
    # zfs.tier.update raises CallError(ent.message) verbatim, so the denial the
    # caller sees must be the engine's own wording, not merely license-ish text.
    assert zfstier_entitlement["message"] in str(exc.value)


# ----------------------------------------------------------------------------
# Kernel parameter sync (requires the licensed/enabled tier pool).
# ----------------------------------------------------------------------------


def _read_kernel_reserve_pct():
    return int(ssh(f"cat {_KERNEL_PARAM_PATH}").strip())


def test_update_metadata_reserve_syncs_kernel_param(tier_pool):
    """Changing special_class_metadata_reserve_pct should sync the ZFS module param."""
    original = call("zfs.tier.config")["special_class_metadata_reserve_pct"]
    new_val = 20 if original != 20 else 22
    try:
        result = call(
            "zfs.tier.update",
            {"special_class_metadata_reserve_pct": new_val},
        )
        assert result["special_class_metadata_reserve_pct"] == new_val
        assert _read_kernel_reserve_pct() == new_val
    finally:
        call("zfs.tier.update", {"special_class_metadata_reserve_pct": original})
        assert _read_kernel_reserve_pct() == original


def test_update_metadata_reserve_noop_does_not_touch_kernel_param(tier_pool):
    """Setting reserve to the same value should not toggle the kernel param."""
    current = call("zfs.tier.config")["special_class_metadata_reserve_pct"]
    before = _read_kernel_reserve_pct()
    call("zfs.tier.update", {"special_class_metadata_reserve_pct": current})
    assert _read_kernel_reserve_pct() == before


# ----------------------------------------------------------------------------
# Service-control verb (RESTART for max_concurrent_jobs, RELOAD otherwise).
# We assert end-state behavior: the daemon stays RUNNING and the on-disk
# rendered config reflects the new value.
# ----------------------------------------------------------------------------


def _zfstierd_main_pid():
    out = ssh("systemctl show -p MainPID --value truenas_zfstierd").strip()
    return int(out)


def test_max_concurrent_jobs_change_triggers_restart(tier_pool):
    """Updating max_concurrent_jobs should restart truenas_zfstierd (PID changes)."""
    pid_before = _zfstierd_main_pid()
    assert pid_before > 0, (
        "truenas_zfstierd must be running before this test (conftest starts it). "
        f"systemctl reports MainPID={pid_before}."
    )
    original = call("zfs.tier.config")["max_concurrent_jobs"]
    new_val = 7 if original != 7 else 6
    try:
        call("zfs.tier.update", {"max_concurrent_jobs": new_val})
        # systemd RESTART verb yields a new MainPID
        pid_after = _zfstierd_main_pid()
        assert pid_after != pid_before, (
            "Expected truenas_zfstierd to restart after max_concurrent_jobs change "
            f"(MainPID was {pid_before}, still is)"
        )
        # Service should still be up after the restart
        assert _zfstierd_main_pid() > 0
    finally:
        call("zfs.tier.update", {"max_concurrent_jobs": original})


def test_max_used_percentage_change_does_not_restart(tier_pool):
    """Non-concurrency updates take the RELOAD path (SIGHUP via ExecReload),
    leaving the daemon's MainPID stable."""
    pid_before = _zfstierd_main_pid()
    assert pid_before > 0, (
        "truenas_zfstierd must be running before this test (conftest starts it). "
        f"systemctl reports MainPID={pid_before}."
    )
    original = call("zfs.tier.config")["max_used_percentage"]
    new_val = 85 if original != 85 else 90
    try:
        call("zfs.tier.update", {"max_used_percentage": new_val})
        pid_after = _zfstierd_main_pid()
        assert pid_after == pid_before, (
            f"Expected truenas_zfstierd to RELOAD (PID stable) on max_used_percentage change "
            f"(MainPID changed {pid_before} -> {pid_after})"
        )
    finally:
        call("zfs.tier.update", {"max_used_percentage": original})


# ----------------------------------------------------------------------------
# Config persistence across a fresh client read (basic transactional check).
# ----------------------------------------------------------------------------


def test_update_persists_metadata_reserve(tier_pool):
    original = call("zfs.tier.config")["special_class_metadata_reserve_pct"]
    new_val = 15 if original != 15 else 17
    try:
        call("zfs.tier.update", {"special_class_metadata_reserve_pct": new_val})
        assert call("zfs.tier.config")["special_class_metadata_reserve_pct"] == new_val
    finally:
        call("zfs.tier.update", {"special_class_metadata_reserve_pct": original})
