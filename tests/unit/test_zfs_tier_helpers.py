"""Pure-helper tests for src/middlewared/middlewared/plugins/zfs/tier.py.

These tests don't need a running middleware daemon or truenas_zfstierd
daemon — they only exercise dict/string/object transformations and the
RewriteClientException → middleware error mapping. They run on a TrueNAS
box where truenas_zfstierd_client and truenas_zfstierd_common are
installed.
"""

import errno

import pytest

from middlewared.plugins.zfs.tier import (
    _map_info_result,
    _map_result_common,
    _parse_tier_job_id,
    _raise_client_error,
)
from middlewared.service_exception import CallError, ValidationError
from truenas_zfstierd_client import RewriteClientException
from truenas_zfstierd_common import (
    CreateJobResult,
    InfoResult,
    JSONRPCError,
    JSONRPCErrorCode,
    RecoverResult,
    RewriteJobStatus,
    RewriteStats,
)


# ----------------------------------------------------------------------------
# Test fixtures (plain helpers; no pytest.fixture for parity with
# tests/unit/test_smb_service.py's top-level-constants style)
# ----------------------------------------------------------------------------


def _stats():
    return RewriteStats(
        start_time=1000,
        initial_time=900,
        update_time=1100,
        count_items=50,
        count_bytes=100 * 1024 * 1024,
        total_items=100,
        total_bytes=200 * 1024 * 1024,
        failures=2,
        success=48,
        parent="/mnt/tank/data",
        name="file.txt",
    )


def _exc(code, message="boom"):
    return RewriteClientException(
        JSONRPCError(code=code, message=message, data=None)
    )


# ----------------------------------------------------------------------------
# _parse_tier_job_id
# ----------------------------------------------------------------------------


def test_parse_tier_job_id_simple():
    ds, uuid = _parse_tier_job_id("tank/data@abc-uuid")
    assert ds == "tank/data"
    assert uuid == "abc-uuid"


def test_parse_tier_job_id_nested_dataset_name():
    ds, uuid = _parse_tier_job_id("tank/foo/bar/baz@xyz")
    assert ds == "tank/foo/bar/baz"
    assert uuid == "xyz"


def test_parse_tier_job_id_real_uuid_with_dashes():
    """The daemon hands back real uuid4 strings — dashes must be preserved."""
    ds, uuid = _parse_tier_job_id(
        "tank/data@deadbeef-0000-1111-2222-333344445555"
    )
    assert ds == "tank/data"
    assert uuid == "deadbeef-0000-1111-2222-333344445555"


def test_parse_tier_job_id_no_at_raises_callerror():
    with pytest.raises(CallError):
        _parse_tier_job_id("no_at_sign_here")


def test_parse_tier_job_id_empty_dataset_raises_callerror():
    with pytest.raises(CallError):
        _parse_tier_job_id("@uuid")


def test_parse_tier_job_id_empty_uuid_raises_callerror():
    with pytest.raises(CallError):
        _parse_tier_job_id("tank/data@")


def test_parse_tier_job_id_empty_raises_callerror():
    with pytest.raises(CallError):
        _parse_tier_job_id("")


def test_parse_tier_job_id_multiple_at_signs_partitions_on_first():
    """str.partition('@') splits at the FIRST '@', so 'a@b@c' → ('a', 'b@c').
    Lock in current behavior so future changes are caught explicitly."""
    ds, uuid = _parse_tier_job_id("a@b@c")
    assert ds == "a"
    assert uuid == "b@c"


# ----------------------------------------------------------------------------
# _map_info_result
# ----------------------------------------------------------------------------


def test_map_info_result_with_complete_stats():
    info = InfoResult(
        dataset_name="tank/data",
        job_uuid="abc",
        status=RewriteJobStatus.RUNNING,
        stats=_stats(),
        error=None,
    )
    out = _map_info_result(info)
    assert out["tier_job_id"] == "tank/data@abc"
    assert out["dataset_name"] == "tank/data"
    assert out["job_uuid"] == "abc"
    assert out["status"] == RewriteJobStatus.RUNNING
    assert out["error"] is None
    assert out["stats"] is not None
    # Spot-check that every input stat field is preserved
    s = out["stats"]
    assert s["start_time"] == 1000
    assert s["initial_time"] == 900
    assert s["update_time"] == 1100
    assert s["count_items"] == 50
    assert s["count_bytes"] == 100 * 1024 * 1024
    assert s["total_items"] == 100
    assert s["total_bytes"] == 200 * 1024 * 1024
    assert s["failures"] == 2
    assert s["success"] == 48
    assert s["parent"] == "/mnt/tank/data"
    assert s["name"] == "file.txt"


def test_map_info_result_no_stats_keeps_none():
    info = InfoResult(
        dataset_name="tank/data",
        job_uuid="abc",
        status=RewriteJobStatus.ERROR,
        stats=None,
        error="permission denied",
    )
    out = _map_info_result(info)
    assert out["stats"] is None
    assert out["error"] == "permission denied"


def test_map_info_result_error_can_be_none_on_completed_job():
    info = InfoResult(
        dataset_name="tank/data",
        job_uuid="abc",
        status=RewriteJobStatus.COMPLETE,
        stats=_stats(),
        error=None,
    )
    out = _map_info_result(info)
    assert out["error"] is None


@pytest.mark.parametrize(
    "status",
    [
        RewriteJobStatus.COMPLETE,
        RewriteJobStatus.RUNNING,
        RewriteJobStatus.QUEUED,
        RewriteJobStatus.CANCELLED,
        RewriteJobStatus.STOPPED,
        RewriteJobStatus.ERROR,
    ],
)
def test_map_info_result_all_statuses_round_trip(status):
    info = InfoResult(
        dataset_name="tank/data",
        job_uuid="abc",
        status=status,
        stats=None,
        error=None,
    )
    out = _map_info_result(info)
    assert out["status"] == status


def test_map_info_result_stats_dict_keys_match_pydantic_model():
    """The dict keys in `stats` must match ZfsTierRewriteJobStats.model_fields
    so the API gateway can validate the response without missing/extra keys."""
    from middlewared.api.v27_0_0.zfs_tier import ZfsTierRewriteJobStats

    info = InfoResult(
        dataset_name="tank/data",
        job_uuid="abc",
        status=RewriteJobStatus.RUNNING,
        stats=_stats(),
        error=None,
    )
    out = _map_info_result(info)
    assert set(out["stats"].keys()) == set(ZfsTierRewriteJobStats.model_fields.keys())


# ----------------------------------------------------------------------------
# _map_result_common
# ----------------------------------------------------------------------------


def test_map_result_common_create_job_result():
    result = CreateJobResult(
        dataset_name="tank/data",
        job_uuid="abc",
        status=RewriteJobStatus.QUEUED,
    )
    out = _map_result_common(result)
    assert out == {
        "tier_job_id": "tank/data@abc",
        "dataset_name": "tank/data",
        "job_uuid": "abc",
        "status": RewriteJobStatus.QUEUED,
    }


def test_map_result_common_recover_result():
    result = RecoverResult(
        dataset_name="tank/data",
        job_uuid="abc",
        status=RewriteJobStatus.RUNNING,
    )
    out = _map_result_common(result)
    assert out["tier_job_id"] == "tank/data@abc"
    assert out["status"] == RewriteJobStatus.RUNNING


def test_map_result_common_dict_keys_match_pydantic_entry():
    """Output shape matches ZfsTierRewriteJobEntry."""
    from middlewared.api.v27_0_0.zfs_tier import ZfsTierRewriteJobEntry

    result = CreateJobResult(
        dataset_name="tank/data",
        job_uuid="abc",
        status=RewriteJobStatus.QUEUED,
    )
    out = _map_result_common(result)
    assert set(out.keys()) == set(ZfsTierRewriteJobEntry.model_fields.keys())


# ----------------------------------------------------------------------------
# _raise_client_error
# ----------------------------------------------------------------------------


def test_raise_client_error_dataset_not_found_to_validation_enoent():
    e = _exc(JSONRPCErrorCode.DATASET_NOT_FOUND, "dataset gone")
    with pytest.raises(ValidationError) as ve:
        _raise_client_error(e, "test_field")
    assert ve.value.errno == errno.ENOENT
    assert ve.value.attribute == "test_field"


def test_raise_client_error_job_not_found_to_validation_enoent():
    e = _exc(JSONRPCErrorCode.JOB_NOT_FOUND, "job gone")
    with pytest.raises(ValidationError) as ve:
        _raise_client_error(e, "tier_job_id")
    assert ve.value.errno == errno.ENOENT
    assert ve.value.attribute == "tier_job_id"


def test_raise_client_error_job_already_exists_to_validation_eexist():
    e = _exc(JSONRPCErrorCode.JOB_ALREADY_EXISTS, "already running")
    with pytest.raises(ValidationError) as ve:
        _raise_client_error(e, "test_field")
    assert ve.value.errno == errno.EEXIST
    assert ve.value.attribute == "test_field"


def test_raise_client_error_disabled_to_callerror():
    e = _exc(JSONRPCErrorCode.DISABLED, "daemon says disabled")
    with pytest.raises(CallError):
        _raise_client_error(e, "test_field")


def test_raise_client_error_operation_failed_falls_through_to_callerror():
    """The daemon raises OPERATION_FAILED (-32003) when recover_job is called
    on a non-ERROR job. The middleware mapper has no special case for it, so
    it falls through to CallError(str(e))."""
    e = _exc(JSONRPCErrorCode.OPERATION_FAILED, "not in ERROR state")
    with pytest.raises(CallError):
        _raise_client_error(e, "test_field")


def test_raise_client_error_parse_error_falls_through_to_callerror():
    e = _exc(JSONRPCErrorCode.PARSE_ERROR, "bad json")
    with pytest.raises(CallError):
        _raise_client_error(e, "test_field")


def test_raise_client_error_preserves_message_in_validation():
    """The daemon's message should appear in the ValidationError errmsg."""
    e = _exc(JSONRPCErrorCode.DATASET_NOT_FOUND, "tank/foo not found")
    with pytest.raises(ValidationError) as ve:
        _raise_client_error(e, "field_name")
    assert "tank/foo not found" in ve.value.errmsg
