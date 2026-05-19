"""Dataset CRUD interactions with tiering: special_small_block_size
validation in pool.dataset.create / update, the INHERIT auto-snap behavior
on create, and pool.snapshot.clone rejection of special_small_blocks
overrides.

Implementation under test:
  - src/middlewared/middlewared/plugins/pool_/dataset.py:324-349, 688-702
  - src/middlewared/middlewared/plugins/zfs/snapshot_crud.py:399-405
"""

import contextlib
import time

import pytest

from middlewared.service_exception import ValidationError, ValidationErrors
from middlewared.test.integration.utils import call


_16M = 16 * 1024 * 1024


def _child(parent, suffix):
    return f"{parent}/{suffix}_{time.monotonic_ns()}"


@contextlib.contextmanager
def _disabled_tiering():
    original = call("zfs.tier.config")["enabled"]
    if not original:
        yield
        return
    call("zfs.tier.update", {"enabled": False})
    try:
        yield
    finally:
        call("zfs.tier.update", {"enabled": original})


# ----------------------------------------------------------------------------
# CREATE: explicit numeric special_small_block_size is rejected.
# ----------------------------------------------------------------------------


def test_create_with_explicit_ssb_rejected_when_tiering_enabled(tier_pool):
    child = _child(tier_pool["name"], "explicit_ssb_create")
    with pytest.raises(ValidationErrors) as ve:
        call(
            "pool.dataset.create",
            {"name": child, "special_small_block_size": 8192},
        )
    msg = ve.value.errors[0].errmsg
    assert "ZFS tiering is enabled" in msg
    assert "zfs.tier.dataset_set_tier" in msg


# ----------------------------------------------------------------------------
# CREATE with INHERIT (or no SSB arg) snaps to PERFORMANCE / REGULAR based on
# the parent's tier (dataset.py:688-702).
# ----------------------------------------------------------------------------


def _child_ssb(parent_ds, suffix):
    """Create child under parent_ds (with no SSB arg) and return its
    special_small_blocks value."""
    child = _child(parent_ds, suffix)
    call("pool.dataset.create", {"name": child})
    try:
        props = call(
            "zfs.resource.query",
            {"paths": [child], "properties": ["special_small_blocks"]},
        )
        return child, props[0]["properties"]["special_small_blocks"]["value"]
    except Exception:
        call("pool.dataset.delete", child, {"recursive": True})
        raise


def test_create_inherit_under_performance_parent_auto_snaps_performance(
    tier_ds_performance,
):
    child, ssb = _child_ssb(tier_ds_performance, "perf_child")
    try:
        assert ssb == _16M, (
            f"Expected child of PERFORMANCE parent to inherit 16M, got {ssb}"
        )
        # And pool.dataset.query should report the child's tier as PERFORMANCE.
        ds = call("pool.dataset.query", [["name", "=", child]], {"get": True})
        assert ds["tier"] is not None
        assert ds["tier"]["tier_type"] == "PERFORMANCE"
    finally:
        call("pool.dataset.delete", child, {"recursive": True})


def test_create_inherit_under_regular_parent_auto_snaps_regular(tier_ds_regular):
    child, ssb = _child_ssb(tier_ds_regular, "reg_child")
    try:
        assert ssb == 0, (
            f"Expected child of REGULAR parent to inherit 0, got {ssb}"
        )
        ds = call("pool.dataset.query", [["name", "=", child]], {"get": True})
        assert ds["tier"] is not None
        assert ds["tier"]["tier_type"] == "REGULAR"
    finally:
        call("pool.dataset.delete", child, {"recursive": True})


def test_create_with_explicit_inherit_string_accepted_when_tiering_enabled(tier_pool):
    """The explicit string 'INHERIT' is the only special_small_block_size value
    accepted on CREATE when tiering is enabled (dataset.py:337-339 reject branch)."""
    child = _child(tier_pool["name"], "inherit_string")
    call("pool.dataset.create", {"name": child, "special_small_block_size": "INHERIT"})
    try:
        # Should land in REGULAR tier (root parent has no SSB set, recordsize default)
        ds = call("pool.dataset.query", [["name", "=", child]], {"get": True})
        assert ds["tier"] is not None
    finally:
        call("pool.dataset.delete", child, {"recursive": True})


# ----------------------------------------------------------------------------
# UPDATE: cannot change special_small_block_size to a different value.
# ----------------------------------------------------------------------------


def test_update_ssb_to_different_value_rejected_when_tiering_enabled(
    tier_ds_regular,
):
    """tier_ds_regular has ssb=0 from the fixture; setting it to 4096 should be rejected."""
    with pytest.raises(ValidationErrors) as ve:
        call(
            "pool.dataset.update",
            tier_ds_regular,
            {"special_small_block_size": 4096},
        )
    msg = ve.value.errors[0].errmsg
    assert "ZFS tiering is enabled" in msg
    assert "zfs.tier.dataset_set_tier" in msg


def test_update_ssb_to_same_numeric_value_allowed_when_tiering_enabled(
    tier_ds_performance,
):
    """No-op resubmission: passing the current parsed value should succeed
    (dataset.py:330-334 'or' clause)."""
    # tier_ds_performance has ssb=16M; resubmitting it should be allowed.
    call(
        "pool.dataset.update",
        tier_ds_performance,
        {"special_small_block_size": _16M},
    )


def test_update_ssb_inherit_when_already_inherited_allowed(tier_ds_regular):
    """The 'INHERIT' branch of the no-op exception only applies if the current
    source is INHERITED/DEFAULT/NONE — not LOCAL. tier_ds_regular has LOCAL
    source after set_tier, so this should be rejected unless we check current source."""
    # Find current source
    props = call(
        "zfs.resource.query",
        {"paths": [tier_ds_regular], "properties": ["special_small_blocks"]},
    )
    source = props[0]["properties"]["special_small_blocks"]["source"]
    # After set_tier, source is LOCAL; INHERIT change is not a no-op and should be rejected.
    if source == "LOCAL":
        with pytest.raises(ValidationErrors) as ve:
            call(
                "pool.dataset.update",
                tier_ds_regular,
                {"special_small_block_size": "INHERIT"},
            )
        assert "ZFS tiering is enabled" in ve.value.errors[0].errmsg
    else:
        # If source was already INHERITED, the INHERIT no-op branch is exercised:
        call(
            "pool.dataset.update",
            tier_ds_regular,
            {"special_small_block_size": "INHERIT"},
        )


# ----------------------------------------------------------------------------
# Tiering-disabled fallback: original 0-16M numeric validation applies, the
# tiering-specific message is not emitted.
# ----------------------------------------------------------------------------


def test_disabled_tiering_falls_back_to_legacy_validation(tier_pool):
    """With tiering disabled, the legacy 0..16M validator kicks in."""
    with _disabled_tiering():
        # Out-of-range value (17 MiB) → legacy error.
        child_over = _child(tier_pool["name"], "legacy_over")
        with pytest.raises(ValidationErrors) as ve:
            call(
                "pool.dataset.create",
                {
                    "name": child_over,
                    "special_small_block_size": 17 * 1024 * 1024,
                },
            )
        msg = ve.value.errors[0].errmsg
        assert "zero to 16M" in msg or "0 to 16M" in msg or "from zero to 16M" in msg
        assert "tiering" not in msg.lower()

        # In-range value (8 KiB) accepted.
        child_ok = _child(tier_pool["name"], "legacy_ok")
        call(
            "pool.dataset.create",
            {"name": child_ok, "special_small_block_size": 8192},
        )
        try:
            props = call(
                "zfs.resource.query",
                {"paths": [child_ok], "properties": ["special_small_blocks"]},
            )
            assert props[0]["properties"]["special_small_blocks"]["value"] == 8192
        finally:
            call("pool.dataset.delete", child_ok, {"recursive": True})


# ----------------------------------------------------------------------------
# pool.snapshot.clone rejects properties={"special_small_blocks": ...}.
# ----------------------------------------------------------------------------


def test_clone_with_ssb_property_override_rejected_when_tiering_enabled(
    tier_ds_regular,
):
    snap_name = f"clone_test_{time.monotonic_ns()}"
    call(
        "pool.snapshot.create",
        {"dataset": tier_ds_regular, "name": snap_name},
    )
    try:
        clone_name = f"{tier_ds_regular}_clone_{time.monotonic_ns()}"
        # snapshot_crud.clone_impl raises a single ValidationError, not a
        # ValidationErrors collection.
        with pytest.raises((ValidationError, ValidationErrors)) as exc:
            call(
                "pool.snapshot.clone",
                {
                    "snapshot": f"{tier_ds_regular}@{snap_name}",
                    "dataset_dst": clone_name,
                    "dataset_properties": {"special_small_blocks": _16M},
                },
            )
        msg = str(exc.value)
        assert "tiering" in msg.lower() or "dataset_set_tier" in msg
        # Make sure clone wasn't created
        clones = call("pool.dataset.query", [["name", "=", clone_name]])
        assert clones == []
    finally:
        call(
            "zfs.resource.snapshot.destroy",
            {"path": f"{tier_ds_regular}@{snap_name}"},
        )


def test_clone_without_ssb_override_allowed(tier_ds_regular):
    """Cloning without overriding special_small_blocks should still work
    when tiering is enabled."""
    snap_name = f"clone_ok_{time.monotonic_ns()}"
    clone_name = f"{tier_ds_regular}_clone_ok_{time.monotonic_ns()}"
    call(
        "pool.snapshot.create",
        {"dataset": tier_ds_regular, "name": snap_name},
    )
    try:
        call(
            "pool.snapshot.clone",
            {
                "snapshot": f"{tier_ds_regular}@{snap_name}",
                "dataset_dst": clone_name,
                "dataset_properties": {},
            },
        )
        # Clone should be visible to pool.dataset.query
        clones = call("pool.dataset.query", [["name", "=", clone_name]])
        assert len(clones) == 1
    finally:
        try:
            call("pool.dataset.delete", clone_name, {"recursive": True})
        except Exception:
            pass
        call(
            "zfs.resource.snapshot.destroy",
            {"path": f"{tier_ds_regular}@{snap_name}"},
        )
