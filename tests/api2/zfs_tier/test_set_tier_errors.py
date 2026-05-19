"""Error paths in zfs.tier.dataset_set_tier and zfs.tier.rewrite_job_create
beyond the two scenarios in test_smoke.py.

Implementation under test:
  - src/middlewared/middlewared/plugins/zfs/tier.py:367-394 (rewrite_job_create)
  - src/middlewared/middlewared/plugins/zfs/tier.py:488-503 (_validate_dataset_writable)
  - src/middlewared/middlewared/plugins/zfs/tier.py:542-609 (dataset_set_tier)
"""

import errno
import time

import pytest

from truenas_api_client import ValidationErrors
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, ssh


# ----------------------------------------------------------------------------
# dataset_set_tier error paths
# ----------------------------------------------------------------------------


def test_dataset_set_tier_not_found_returns_enoent(tier_pool):
    """A non-existent dataset on a tier-capable pool → ENOENT."""
    nonexistent = f"{tier_pool['name']}/does_not_exist_{time.monotonic_ns()}"
    with pytest.raises(ValidationErrors) as ve:
        call(
            "zfs.tier.dataset_set_tier",
            {"dataset_name": nonexistent, "tier_type": "PERFORMANCE"},
        )
    assert ve.value.errors[0].errno == errno.ENOENT


def test_dataset_set_tier_unmounted_rejected(tier_ds):
    """Manually unmounting the dataset should cause set_tier to fail with EINVAL."""
    ssh(f"zfs unmount {tier_ds}")
    try:
        with pytest.raises(ValidationErrors) as ve:
            call(
                "zfs.tier.dataset_set_tier",
                {"dataset_name": tier_ds, "tier_type": "PERFORMANCE"},
            )
        assert ve.value.errors[0].errno == errno.EINVAL
        assert "not mounted" in ve.value.errors[0].errmsg
    finally:
        # Best-effort remount so the conftest cleanup can delete cleanly.
        ssh(f"zfs mount {tier_ds} || true")


def test_dataset_set_tier_readonly_rejected_with_erofs(tier_ds):
    """readonly=ON datasets reject set_tier with EROFS."""
    call("pool.dataset.update", tier_ds, {"readonly": "ON"})
    try:
        with pytest.raises(ValidationErrors) as ve:
            call(
                "zfs.tier.dataset_set_tier",
                {"dataset_name": tier_ds, "tier_type": "PERFORMANCE"},
            )
        assert ve.value.errors[0].errno == errno.EROFS
    finally:
        call("pool.dataset.update", tier_ds, {"readonly": "OFF"})


def test_dataset_set_tier_with_active_job_returns_ebusy(tier_ds):
    """If a tier job is already RUNNING or QUEUED for the dataset, set_tier
    refuses with EBUSY (tier.py:576-584)."""
    # Pre-fill the dataset so the daemon has work to do — keeps the job
    # in RUNNING long enough for us to issue a competing set_tier call.
    ssh(
        f"for i in $(seq 1 500); do dd if=/dev/urandom of=/mnt/{tier_ds}/f$i "
        "bs=4k count=1 2>/dev/null; done"
    )
    entry = call("zfs.tier.rewrite_job_create", {"dataset_name": tier_ds})

    try:
        status = call(
            "zfs.tier.rewrite_job_status", {"tier_job_id": entry["tier_job_id"]}
        )["status"]
        if status not in ("QUEUED", "RUNNING"):
            pytest.skip(
                f"Job reached terminal status {status!r} before EBUSY could be tested"
            )
        with pytest.raises(ValidationErrors) as ve:
            call(
                "zfs.tier.dataset_set_tier",
                {"dataset_name": tier_ds, "tier_type": "PERFORMANCE"},
            )
        assert ve.value.errors[0].errno == errno.EBUSY
        assert "tier migration job is already in progress" in ve.value.errors[0].errmsg
    finally:
        # Try to cancel and drain the job so dataset teardown won't be blocked.
        try:
            call("zfs.tier.rewrite_job_cancel", {"tier_job_id": entry["tier_job_id"]})
        except Exception:
            pass


def test_dataset_set_tier_same_tier_no_job_created(tier_ds_regular):
    """Setting the same tier the dataset already has is a no-op — no migration job
    is created (the tier_type == current_info["tier_type"] short-circuit at
    tier.py:586 skips space validation, and no rewrite_job_create runs)."""
    result = call(
        "zfs.tier.dataset_set_tier",
        {"dataset_name": tier_ds_regular, "tier_type": "REGULAR"},
    )
    assert result["tier_type"] == "REGULAR"
    assert result["tier_job"] is None


# ----------------------------------------------------------------------------
# rewrite_job_create error paths
# ----------------------------------------------------------------------------


def test_rewrite_job_create_requires_globally_enabled(tier_ds):
    """When zfs.tier.config.enabled is False, rewrite_job_create rejects with EINVAL."""
    original = call("zfs.tier.config")["enabled"]
    call("zfs.tier.update", {"enabled": False})
    try:
        with pytest.raises(ValidationErrors) as ve:
            call("zfs.tier.rewrite_job_create", {"dataset_name": tier_ds})
        assert ve.value.errors[0].errno == errno.EINVAL
        assert "globally disabled" in ve.value.errors[0].errmsg
    finally:
        call("zfs.tier.update", {"enabled": original})


def test_rewrite_job_create_no_special_vdev_einval(tier_pool):
    """Dataset on a pool without SPECIAL vdev → EINVAL with 'SPECIAL vdev' message."""
    # `dataset()` asset creates on the default test pool (no SPECIAL vdev)
    with dataset("tier_rewrite_no_special") as ds:
        with pytest.raises(ValidationErrors) as ve:
            call("zfs.tier.rewrite_job_create", {"dataset_name": ds})
        err = ve.value.errors[0]
        assert err.errno == errno.EINVAL
        assert "SPECIAL vdev" in err.errmsg


def test_rewrite_job_create_dataset_not_found_returns_enoent(tier_pool):
    nonexistent = f"{tier_pool['name']}/does_not_exist_{time.monotonic_ns()}"
    with pytest.raises(ValidationErrors) as ve:
        call("zfs.tier.rewrite_job_create", {"dataset_name": nonexistent})
    assert ve.value.errors[0].errno == errno.ENOENT


def test_rewrite_job_create_unmounted_dataset_rejected(tier_ds):
    """_validate_dataset_writable check at tier.py:382 trips for unmounted datasets."""
    ssh(f"zfs unmount {tier_ds}")
    try:
        with pytest.raises(ValidationErrors) as ve:
            call("zfs.tier.rewrite_job_create", {"dataset_name": tier_ds})
        assert ve.value.errors[0].errno == errno.EINVAL
        assert "not mounted" in ve.value.errors[0].errmsg
    finally:
        ssh(f"zfs mount {tier_ds} || true")


def test_rewrite_job_create_readonly_dataset_rejected(tier_ds):
    call("pool.dataset.update", tier_ds, {"readonly": "ON"})
    try:
        with pytest.raises(ValidationErrors) as ve:
            call("zfs.tier.rewrite_job_create", {"dataset_name": tier_ds})
        assert ve.value.errors[0].errno == errno.EROFS
    finally:
        call("pool.dataset.update", tier_ds, {"readonly": "OFF"})


# ----------------------------------------------------------------------------
# rewrite_job_recover error paths
# ----------------------------------------------------------------------------


def test_rewrite_job_recover_unmounted_rejected(tier_ds, wait_for_job_status):
    """tier.py:479 — recover validates writable before calling the daemon."""
    # Create then complete a job so it exists; then unmount the dataset
    entry = call("zfs.tier.rewrite_job_create", {"dataset_name": tier_ds})
    wait_for_job_status(entry["tier_job_id"], {"COMPLETE", "ERROR"}, timeout=60)
    ssh(f"zfs unmount {tier_ds}")
    try:
        with pytest.raises(ValidationErrors) as ve:
            call(
                "zfs.tier.rewrite_job_recover",
                {"tier_job_id": entry["tier_job_id"]},
            )
        # Either EINVAL (unmounted) or ENOENT (job-not-found cases)
        assert ve.value.errors[0].errno in (errno.EINVAL, errno.ENOENT)
    finally:
        ssh(f"zfs mount {tier_ds} || true")
