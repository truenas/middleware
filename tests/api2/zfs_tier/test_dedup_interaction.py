"""Deduplication conflicts with PERFORMANCE-tier placement, not tiering as such.

A dataset is excluded from tiering (reports ``tier: None`` in every query path)
whenever its effective deduplication value is other than off. Enabling
deduplication is refused only when dedup'd data would land on the SPECIAL
vdev: the dataset itself is (or inherits) the PERFORMANCE tier
(special_small_blocks > 0), or a descendant that would inherit the new
deduplication value is. REGULAR datasets (data on the normal vdev), volumes,
and datasets on pools without a SPECIAL vdev may be deduplicated freely.

Implementation under test:
  - src/middlewared/middlewared/plugins/zfs/tier.py
    (get_dataset_tier_info_cached dedup gate, _dataset_dedup_enabled,
    dataset_set_tier / rewrite_job_create rejection messages)
  - src/middlewared/middlewared/plugins/pool_/utils.py (validate_dedup_tiering,
    _dedup_inheriting_performance_descendants, pool_has_special_vdev)
"""

import contextlib
import errno
import time

import pytest

from middlewared.service_exception import ValidationError, ValidationErrors
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call


INCOMPATIBLE_MSG = "incompatible with tiering"


@pytest.fixture(scope="module", autouse=True)
def _require_dedup_feature(tier_pool):
    """validate_dedup_license would reject dedup before the tiering check runs
    on licensed systems without the DEDUP feature flag."""
    if call("system.license") is not None and not call("system.feature_enabled", "DEDUP"):
        pytest.skip("System license does not include the ZFS deduplication feature")


def _child(parent, suffix):
    return f"{parent}/{suffix}_{time.monotonic_ns()}"


@contextlib.contextmanager
def _dedup_dataset(tier_pool, suffix):
    """A dedup'd REGULAR dataset on the tier pool. REGULAR datasets keep their
    data on the normal vdev, so they may be deduplicated with tiering enabled."""
    ds = _child(tier_pool["name"], suffix)
    call("pool.dataset.create", {"name": ds, "deduplication": "ON"})
    try:
        yield ds
    finally:
        call("pool.dataset.delete", ds, {"recursive": True})


# ----------------------------------------------------------------------------
# Display: dedup'd datasets report tier=None in every query path.
# ----------------------------------------------------------------------------


def test_dedup_dataset_tier_is_none_in_queries(tier_pool):
    with _dedup_dataset(tier_pool, "dedup_disp") as ds:
        row = call("pool.dataset.query", [["name", "=", ds]], {"get": True})
        assert row.get("tier") is None

        rows = call("zfs.resource.query", {"paths": [ds], "get_tier": True})
        assert rows
        assert rows[0].get("tier") is None

        # Control: a sibling without dedup on the same pool reports a tier.
        control = _child(tier_pool["name"], "dedup_disp_control")
        call("pool.dataset.create", {"name": control})
        try:
            row = call("pool.dataset.query", [["name", "=", control]], {"get": True})
            assert row["tier"] is not None
        finally:
            call("pool.dataset.delete", control, {"recursive": True})


def test_inherited_dedup_child_tier_is_none(tier_pool):
    """The tier display keys off the effective deduplication value: a child
    inheriting dedup from its parent is excluded from tiering too, and creating
    such a child (deduplication left at INHERIT) is allowed."""
    with _dedup_dataset(tier_pool, "dedup_parent") as parent:
        child = _child(parent, "inherit_child")
        call("pool.dataset.create", {"name": child})
        row = call("pool.dataset.query", [["name", "=", child]], {"get": True})
        assert row["deduplication"]["value"] == "ON"
        assert row.get("tier") is None


# ----------------------------------------------------------------------------
# pool.dataset create/update: dedup is allowed on REGULAR placement, refused on
# PERFORMANCE placement (data on the SPECIAL vdev).
# ----------------------------------------------------------------------------


@pytest.mark.parametrize("dedup", ["ON", "VERIFY"])
def test_create_dedup_allowed_under_regular_parent(tier_pool, dedup):
    """A new dataset with REGULAR placement (the default; data on the normal
    vdev) may be created with deduplication enabled while tiering is on. It then
    drops out of tiering (tier=None)."""
    ds = _child(tier_pool["name"], "dedup_regular_create")
    call("pool.dataset.create", {"name": ds, "deduplication": dedup})
    try:
        row = call("pool.dataset.query", [["name", "=", ds]], {"get": True})
        assert row["deduplication"]["value"] == dedup
        assert row.get("tier") is None
    finally:
        call("pool.dataset.delete", ds, {"recursive": True})


@pytest.mark.parametrize("dedup", ["ON", "VERIFY"])
def test_create_dedup_rejected_under_performance_parent(tier_ds_performance, dedup):
    """A new child inheriting PERFORMANCE placement (data on the SPECIAL vdev)
    cannot be created with deduplication enabled."""
    child = _child(tier_ds_performance, "dedup_child")
    with pytest.raises(ValidationErrors) as ve:
        call("pool.dataset.create", {"name": child, "deduplication": dedup})
    error = ve.value.errors[0]
    assert error.attribute == "pool_dataset_create.deduplication"
    assert INCOMPATIBLE_MSG in error.errmsg
    assert call("pool.dataset.query", [["name", "=", child]]) == []


def test_update_enabling_dedup_allowed_on_regular_dataset(tier_ds):
    """A REGULAR dataset (data on the normal vdev) may have dedup enabled while
    tiering is on; it then drops out of tiering (tier=None)."""
    call("pool.dataset.update", tier_ds, {"deduplication": "ON"})
    row = call("pool.dataset.query", [["name", "=", tier_ds]], {"get": True})
    assert row["deduplication"]["value"] == "ON"
    assert row.get("tier") is None


def test_update_enabling_dedup_rejected_on_performance_dataset(tier_ds_performance):
    """A PERFORMANCE dataset (data on the SPECIAL vdev) cannot have dedup
    enabled."""
    with pytest.raises(ValidationErrors) as ve:
        call("pool.dataset.update", tier_ds_performance, {"deduplication": "ON"})
    error = ve.value.errors[0]
    assert error.attribute == "pool_dataset_update.deduplication"
    assert INCOMPATIBLE_MSG in error.errmsg


def test_update_enabling_dedup_rejected_with_performance_descendant(tier_ds):
    """Deduplication is inherited: enabling it on a REGULAR dataset is refused
    when a descendant without its own deduplication setting is assigned to the
    PERFORMANCE tier (the change would land dedup'd data on the SPECIAL vdev)."""
    mid = _child(tier_ds, "mid")
    grandchild = _child(mid, "perf_grandchild")
    call("pool.dataset.create", {"name": mid})
    call("pool.dataset.create", {"name": grandchild})
    call(
        "zfs.tier.dataset_set_tier",
        {"dataset_name": grandchild, "tier_type": "PERFORMANCE"},
    )

    with pytest.raises(ValidationErrors) as ve:
        call("pool.dataset.update", tier_ds, {"deduplication": "ON"})
    error = ve.value.errors[0]
    assert error.attribute == "pool_dataset_update.deduplication"
    assert INCOMPATIBLE_MSG in error.errmsg
    assert grandchild in error.errmsg


def test_update_enabling_dedup_allowed_when_performance_descendant_masked(tier_ds):
    """A PERFORMANCE descendant with its own local deduplication=OFF is not
    affected by the ancestor's change, so it neither blocks enabling dedup nor
    loses its tier."""
    child = _child(tier_ds, "perf_child_masked")
    call("pool.dataset.create", {"name": child, "deduplication": "OFF"})
    call(
        "zfs.tier.dataset_set_tier",
        {"dataset_name": child, "tier_type": "PERFORMANCE"},
    )

    call("pool.dataset.update", tier_ds, {"deduplication": "ON"})
    row = call("pool.dataset.query", [["name", "=", child]], {"get": True})
    assert row["deduplication"]["value"] == "OFF"
    assert row["tier"] is not None


def test_dedup_toggles_freely_on_regular_dataset(tier_pool):
    """A REGULAR dataset's data is on the normal vdev, so deduplication can be
    switched, disabled, and re-enabled freely with tiering on."""
    with _dedup_dataset(tier_pool, "dedup_toggle") as ds:
        call("pool.dataset.update", ds, {"deduplication": "VERIFY"})
        call("pool.dataset.update", ds, {"deduplication": "OFF"})
        call("pool.dataset.update", ds, {"deduplication": "ON"})


def test_dedup_allowed_on_pool_without_special_vdev(tier_pool):
    """Tiering globally enabled, but the primary pool has no SPECIAL vdev:
    deduplication stays usable there, and such datasets keep reporting
    tier=None like any dataset on a pool that does not support tiering."""
    with dataset("dedup_no_special", {"deduplication": "ON"}) as ds:
        call("pool.dataset.update", ds, {"deduplication": "VERIFY"})
        row = call("pool.dataset.query", [["name", "=", ds]], {"get": True})
        assert row.get("tier") is None


def test_dedup_allowed_on_zvol_on_tiered_pool(tier_pool):
    """Volumes are never tiered, so deduplication is allowed on a ZVOL even on a
    SPECIAL-vdev pool with tiering enabled (create and update), and the volume
    carries no tier."""
    zvol = _child(tier_pool["name"], "dedup_zvol")
    call(
        "pool.dataset.create",
        {
            "name": zvol,
            "type": "VOLUME",
            "volsize": 1048576,
            "sparse": True,
            "deduplication": "ON",
        },
    )
    try:
        row = call("pool.dataset.query", [["name", "=", zvol]], {"get": True})
        assert row["deduplication"]["value"] == "ON"
        assert row.get("tier") is None
        # The update path is exempt for volumes too.
        call("pool.dataset.update", zvol, {"deduplication": "VERIFY"})
    finally:
        call("pool.dataset.delete", zvol, {"recursive": True})


# ----------------------------------------------------------------------------
# zfs.tier.dataset_set_tier / rewrite_job_create refuse dedup'd datasets.
# ----------------------------------------------------------------------------


def test_set_tier_rejected_on_dedup_dataset(tier_pool):
    with _dedup_dataset(tier_pool, "dedup_settier") as ds:
        with pytest.raises(ValidationError) as ve:
            call(
                "zfs.tier.dataset_set_tier",
                {"dataset_name": ds, "tier_type": "PERFORMANCE"},
            )
        assert ve.value.errno == errno.EINVAL
        assert "deduplication" in ve.value.errmsg


def test_rewrite_job_create_rejected_on_dedup_dataset(tier_pool):
    with _dedup_dataset(tier_pool, "dedup_rw") as ds:
        with pytest.raises(ValidationError) as ve:
            call("zfs.tier.rewrite_job_create", {"dataset_name": ds})
        assert ve.value.errno == errno.EINVAL
        assert "deduplication" in ve.value.errmsg


def test_tier_errors_prefer_pool_reason_without_special_vdev(tier_pool):
    """On a pool without a SPECIAL vdev the tier APIs report the pool as the
    reason even when the dataset is deduplicated — disabling deduplication
    would not make such a dataset tierable."""
    with dataset("dedup_no_special_msg", {"deduplication": "ON"}) as ds:
        with pytest.raises(ValidationError) as ve:
            call(
                "zfs.tier.dataset_set_tier",
                {"dataset_name": ds, "tier_type": "PERFORMANCE"},
            )
        assert ve.value.errno == errno.EINVAL
        assert "pool has no SPECIAL vdev" in ve.value.errmsg

        with pytest.raises(ValidationError) as ve:
            call("zfs.tier.rewrite_job_create", {"dataset_name": ds})
        assert ve.value.errno == errno.EINVAL
        assert "pool has no SPECIAL vdev" in ve.value.errmsg
