"""Pydantic model validation tests for the zfs.tier API surface.

These tests run on the TrueNAS box (or anywhere middleware is importable);
they don't talk to a daemon or a database. They lock down the shape that
the JSON-RPC gateway will enforce on inputs and outputs.
"""

import pytest
from pydantic import ValidationError

from middlewared.api.v26_0_0.zfs_tier import (
    TierInfo,
    ZfsTierDatasetSetTierArgs,
    ZfsTierEntry,
    ZfsTierRewriteJobCreateArgs,
    ZfsTierRewriteJobEntry,
    ZfsTierRewriteJobQueryArgs,
    ZfsTierRewriteJobStats,
    ZfsTierRewriteJobStatusEntry,
    ZfsTierRewriteJobStatusEventSourceArgs,
    ZfsTierUpdateArgs,
)
from middlewared.api.v26_0_0.smb import SharingSMBUpdateArgs
from middlewared.api.v26_0_0.nfs import SharingNFSUpdateArgs


# ----------------------------------------------------------------------------
# ZfsTierEntry: full config record
# ----------------------------------------------------------------------------


_VALID_ENTRY = {
    "id": 1,
    "enabled": True,
    "max_concurrent_jobs": 5,
    "max_used_percentage": 80,
    "special_class_metadata_reserve_pct": 25,
}


def test_entry_valid_construct():
    entry = ZfsTierEntry(**_VALID_ENTRY)
    assert entry.id == 1
    assert entry.enabled is True
    assert entry.max_concurrent_jobs == 5
    assert entry.max_used_percentage == 80
    assert entry.special_class_metadata_reserve_pct == 25


def test_entry_rejects_max_concurrent_jobs_below_min():
    with pytest.raises(ValidationError):
        ZfsTierEntry(**(_VALID_ENTRY | {"max_concurrent_jobs": 0}))


def test_entry_rejects_max_concurrent_jobs_above_max():
    with pytest.raises(ValidationError):
        ZfsTierEntry(**(_VALID_ENTRY | {"max_concurrent_jobs": 11}))


def test_entry_rejects_max_used_percentage_below_70():
    with pytest.raises(ValidationError):
        ZfsTierEntry(**(_VALID_ENTRY | {"max_used_percentage": 69}))


def test_entry_rejects_max_used_percentage_above_95():
    with pytest.raises(ValidationError):
        ZfsTierEntry(**(_VALID_ENTRY | {"max_used_percentage": 96}))


def test_entry_rejects_metadata_reserve_below_10():
    with pytest.raises(ValidationError):
        ZfsTierEntry(**(_VALID_ENTRY | {"special_class_metadata_reserve_pct": 9}))


def test_entry_rejects_metadata_reserve_above_30():
    with pytest.raises(ValidationError):
        ZfsTierEntry(**(_VALID_ENTRY | {"special_class_metadata_reserve_pct": 31}))


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_concurrent_jobs", 1),
        ("max_concurrent_jobs", 10),
        ("max_used_percentage", 70),
        ("max_used_percentage", 95),
        ("special_class_metadata_reserve_pct", 10),
        ("special_class_metadata_reserve_pct", 30),
    ],
)
def test_entry_accepts_boundary_values(field, value):
    ZfsTierEntry(**(_VALID_ENTRY | {field: value}))


# ----------------------------------------------------------------------------
# ZfsTierUpdateArgs: excludes `id`, all fields optional (ForUpdateMetaclass)
# ----------------------------------------------------------------------------


def test_update_args_rejects_id_field():
    """Excluded field — passing id should raise 'Extra inputs are not permitted'."""
    with pytest.raises(ValidationError):
        ZfsTierUpdateArgs(zfs_tier_update={"id": 1, "enabled": True})


def test_update_args_empty_dict_validates():
    """ForUpdateMetaclass makes every field optional."""
    args = ZfsTierUpdateArgs(zfs_tier_update={})
    # Verify shape: model_dump should return only non-NotRequired fields.
    args.model_dump()


def test_update_args_partial_validates_bounds():
    """Partial updates still go through bounds validation."""
    with pytest.raises(ValidationError):
        ZfsTierUpdateArgs(zfs_tier_update={"max_concurrent_jobs": 11})


def test_update_args_accepts_partial_valid_update():
    ZfsTierUpdateArgs(zfs_tier_update={"max_concurrent_jobs": 5})


# ----------------------------------------------------------------------------
# TierInfo: StorageTier literal validation
# ----------------------------------------------------------------------------


def test_tier_info_accepts_performance():
    info = TierInfo(tier_type="PERFORMANCE")
    assert info.tier_type == "PERFORMANCE"
    assert info.tier_job is None


def test_tier_info_accepts_regular():
    info = TierInfo(tier_type="REGULAR")
    assert info.tier_type == "REGULAR"


def test_tier_info_rejects_invalid_tier_type():
    with pytest.raises(ValidationError):
        TierInfo(tier_type="FAST")


def test_tier_info_tier_job_defaults_to_none():
    info = TierInfo(tier_type="PERFORMANCE")
    assert info.tier_job is None


def test_tier_info_with_tier_job():
    info = TierInfo(
        tier_type="PERFORMANCE",
        tier_job={
            "tier_job_id": "tank/data@abc-uuid",
            "dataset_name": "tank/data",
            "job_uuid": "abc-uuid",
            "status": "RUNNING",
        },
    )
    assert info.tier_job is not None
    assert info.tier_job.status == "RUNNING"


# ----------------------------------------------------------------------------
# ZfsTierRewriteJobEntry: status enum + NonEmptyString
# ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "status",
    ["COMPLETE", "RUNNING", "QUEUED", "CANCELLED", "STOPPED", "ERROR"],
)
def test_rewrite_job_entry_accepts_each_status(status):
    e = ZfsTierRewriteJobEntry(
        tier_job_id="tank/data@uuid",
        dataset_name="tank/data",
        job_uuid="uuid",
        status=status,
    )
    assert e.status == status


def test_rewrite_job_entry_rejects_unknown_status():
    with pytest.raises(ValidationError):
        ZfsTierRewriteJobEntry(
            tier_job_id="tank/data@uuid",
            dataset_name="tank/data",
            job_uuid="uuid",
            status="BOGUS",
        )


def test_rewrite_job_entry_rejects_empty_tier_job_id():
    with pytest.raises(ValidationError):
        ZfsTierRewriteJobEntry(
            tier_job_id="",
            dataset_name="tank/data",
            job_uuid="uuid",
            status="RUNNING",
        )


def test_rewrite_job_entry_rejects_empty_dataset_name():
    with pytest.raises(ValidationError):
        ZfsTierRewriteJobEntry(
            tier_job_id="tank/data@uuid",
            dataset_name="",
            job_uuid="uuid",
            status="RUNNING",
        )


# ----------------------------------------------------------------------------
# ZfsTierRewriteJobStatusEventSourceArgs: subscribe by tier_job_id
# ----------------------------------------------------------------------------


def test_status_event_source_args_valid_tier_job_id():
    args = ZfsTierRewriteJobStatusEventSourceArgs(tier_job_id="tank/data@uuid")
    assert args.tier_job_id == "tank/data@uuid"


def test_status_event_source_args_rejects_empty_tier_job_id():
    with pytest.raises(ValidationError):
        ZfsTierRewriteJobStatusEventSourceArgs(tier_job_id="")


# ----------------------------------------------------------------------------
# ZfsTierRewriteJobStatusEntry: stats and error are optional, nullable
# ----------------------------------------------------------------------------


_STATS_DICT = {
    "start_time": 1000,
    "initial_time": 900,
    "update_time": 1100,
    "count_items": 50,
    "count_bytes": 100 * 1024 * 1024,
    "total_items": 100,
    "total_bytes": 200 * 1024 * 1024,
    "failures": 2,
    "success": 48,
    "parent": "/mnt/tank/data",
    "name": "file.txt",
}


def test_status_entry_stats_can_be_none():
    e = ZfsTierRewriteJobStatusEntry(
        tier_job_id="tank/data@uuid",
        dataset_name="tank/data",
        job_uuid="uuid",
        status="RUNNING",
        stats=None,
        error=None,
    )
    assert e.stats is None


def test_status_entry_stats_dict_validates():
    e = ZfsTierRewriteJobStatusEntry(
        tier_job_id="tank/data@uuid",
        dataset_name="tank/data",
        job_uuid="uuid",
        status="RUNNING",
        stats=_STATS_DICT,
        error=None,
    )
    assert isinstance(e.stats, ZfsTierRewriteJobStats)
    assert e.stats.count_items == 50


def test_status_entry_error_is_string_or_none():
    e_with = ZfsTierRewriteJobStatusEntry(
        tier_job_id="tank/data@uuid",
        dataset_name="tank/data",
        job_uuid="uuid",
        status="ERROR",
        stats=None,
        error="permission denied",
    )
    assert e_with.error == "permission denied"


# ----------------------------------------------------------------------------
# ZfsTierDatasetSetTierArgs: defaults and required fields
# ----------------------------------------------------------------------------


def test_set_tier_args_move_existing_data_defaults_false():
    args = ZfsTierDatasetSetTierArgs(
        zfs_tier_dataset_set_tier={
            "dataset_name": "tank/data",
            "tier_type": "PERFORMANCE",
        }
    )
    payload = args.zfs_tier_dataset_set_tier
    assert payload.move_existing_data is False


def test_set_tier_args_accepts_move_existing_data_true():
    args = ZfsTierDatasetSetTierArgs(
        zfs_tier_dataset_set_tier={
            "dataset_name": "tank/data",
            "tier_type": "REGULAR",
            "move_existing_data": True,
        }
    )
    assert args.zfs_tier_dataset_set_tier.move_existing_data is True


def test_set_tier_args_requires_dataset_name():
    with pytest.raises(ValidationError):
        ZfsTierDatasetSetTierArgs(
            zfs_tier_dataset_set_tier={"tier_type": "PERFORMANCE"}
        )


def test_set_tier_args_requires_tier_type():
    with pytest.raises(ValidationError):
        ZfsTierDatasetSetTierArgs(
            zfs_tier_dataset_set_tier={"dataset_name": "tank/data"}
        )


def test_set_tier_args_rejects_unknown_tier_type():
    with pytest.raises(ValidationError):
        ZfsTierDatasetSetTierArgs(
            zfs_tier_dataset_set_tier={
                "dataset_name": "tank/data",
                "tier_type": "FAST",
            }
        )


# ----------------------------------------------------------------------------
# ZfsTierRewriteJobCreateArgs
# ----------------------------------------------------------------------------


def test_rewrite_job_create_args_requires_dataset_name():
    with pytest.raises(ValidationError):
        ZfsTierRewriteJobCreateArgs(zfs_tier_rewrite_job_create={})


def test_rewrite_job_create_args_rejects_empty_dataset_name():
    with pytest.raises(ValidationError):
        ZfsTierRewriteJobCreateArgs(zfs_tier_rewrite_job_create={"dataset_name": ""})


# ----------------------------------------------------------------------------
# ZfsTierRewriteJobQueryArgs: aliased filters/options + default status=None
# ----------------------------------------------------------------------------


def test_rewrite_job_query_args_default_status_is_none():
    args = ZfsTierRewriteJobQueryArgs(zfs_tier_rewrite_job_query={})
    assert args.zfs_tier_rewrite_job_query.status is None


def test_rewrite_job_query_args_aliased_filters_and_options():
    """query-filters and query-options are aliased dict keys (Field alias='...')."""
    args = ZfsTierRewriteJobQueryArgs(
        zfs_tier_rewrite_job_query={
            "status": ["RUNNING", "COMPLETE"],
            "query-filters": [],
            "query-options": {"limit": 5},
        }
    )
    inner = args.zfs_tier_rewrite_job_query
    assert inner.status == ["RUNNING", "COMPLETE"]
    # query_filters/options are Pydantic-typed, exact representation depends on
    # framework — but at minimum they must not have raised.


def test_rewrite_job_query_args_rejects_bogus_status_in_list():
    with pytest.raises(ValidationError):
        ZfsTierRewriteJobQueryArgs(zfs_tier_rewrite_job_query={"status": ["BOGUS"]})


# ----------------------------------------------------------------------------
# Share update API: `tier` is Excluded
# ----------------------------------------------------------------------------


def test_sharing_smb_update_excludes_tier():
    """SmbShareUpdate (the `data` model on SharingSMBUpdateArgs) rejects a
    `tier` field — it's Excluded() at api/v26_0_0/smb.py:840."""
    with pytest.raises(ValidationError):
        SharingSMBUpdateArgs(
            id=1,
            data={"tier": {"tier_type": "PERFORMANCE", "tier_job": None}},
        )


def test_sharing_nfs_update_excludes_tier():
    """NfsShareUpdate rejects a `tier` field — Excluded() at api/v26_0_0/nfs.py:191."""
    with pytest.raises(ValidationError):
        SharingNFSUpdateArgs(
            id=1,
            data={"tier": {"tier_type": "PERFORMANCE", "tier_job": None}},
        )
