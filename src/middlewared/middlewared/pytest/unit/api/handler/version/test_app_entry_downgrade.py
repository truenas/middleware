import pytest

from middlewared.api.base.handler.accept import validate_model
from middlewared.api.base.handler.version import APIVersion, APIVersionsAdapter
from middlewared.api.v26_0_0.app import AppEntry as AppEntry_v26_0_0
from middlewared.api.v27_0_0.app import AppEntry as AppEntry_v27_0_0
from middlewared.service.crud_service import get_instance_result
from middlewared.service_exception import ValidationErrors

from .utils import TestModelProvider

MODEL_NAME = "AppGetInstanceResult"
AppGetInstanceResult_v26_0_0 = get_instance_result(AppEntry_v26_0_0)
AppGetInstanceResult_v27_0_0 = get_instance_result(AppEntry_v27_0_0)


def _build_adapter():
    return APIVersionsAdapter(
        [
            APIVersion("v26.0.0", TestModelProvider({MODEL_NAME: AppGetInstanceResult_v26_0_0})),
            APIVersion("v27.0.0", TestModelProvider({MODEL_NAME: AppGetInstanceResult_v27_0_0})),
        ]
    )


def app_entry(**overrides):
    return {
        "name": "actual-budget",
        "id": "actual-budget",
        "state": "RUNNING",
        "error_reason": None,
        "upgrade_available": False,
        "latest_version": None,
        "latest_app_version": None,
        "image_updates_available": False,
        "custom_app": False,
        "migrated": False,
        "human_version": "24.10.1_1.1.13",
        "version": "1.1.13",
        "metadata": {"name": "actual-budget", "train": "community", "version": "1.1.13"},
        "active_workloads": {
            "containers": 0,
            "used_ports": [],
            "used_host_ips": [],
            "container_details": [],
            "volumes": [],
            "images": [],
            "networks": [],
        },
        "notes": None,
        "action_required": False,
        "portals": {},
    } | overrides


def error_app_entry(**overrides):
    return app_entry(
        **{
            "state": "ERROR",
            "error_reason": "METADATA_UNREADABLE",
            "version": None,
            "human_version": None,
            "metadata": {},
        }
        | overrides
    )


async def adapt(value):
    return await _build_adapter().adapt({"result": value}, MODEL_NAME, "v27.0.0", "v26.0.0")


@pytest.mark.asyncio
async def test_error_state_is_reported_as_crashed():
    result = (await adapt(error_app_entry()))["result"]

    assert result["state"] == "CRASHED"


@pytest.mark.asyncio
async def test_null_versions_are_filled_in():
    result = (await adapt(error_app_entry()))["result"]

    assert result["version"] == "unknown"
    assert result["human_version"] == "unknown"


@pytest.mark.asyncio
async def test_error_reason_is_dropped():
    result = (await adapt(error_app_entry()))["result"]

    assert "error_reason" not in result


@pytest.mark.asyncio
async def test_downgraded_error_app_is_valid_for_the_older_version():
    # Without the substitutions above this raises, and in production it would instead be silently
    # logged and the newer shape handed to the client anyway
    adapted = await adapt(error_app_entry())

    validate_model(AppGetInstanceResult_v26_0_0, adapted)


@pytest.mark.asyncio
async def test_healthy_app_is_unchanged():
    result = (await adapt(app_entry()))["result"]

    assert result["state"] == "RUNNING"
    assert result["version"] == "1.1.13"
    assert result["human_version"] == "24.10.1_1.1.13"


def test_partial_entry_is_tolerated():
    # `app.query` supports `select`, and its result items have every field optional, so the
    # conversion has to cope with only a subset of them being present
    result = AppEntry_v27_0_0.to_previous({"state": "ERROR"})

    assert result["state"] == "CRASHED"
    assert "version" not in result
    assert "human_version" not in result


@pytest.mark.asyncio
async def test_error_state_is_rejected_by_the_older_version_directly():
    with pytest.raises(ValidationErrors):
        validate_model(AppGetInstanceResult_v26_0_0, {"result": error_app_entry()})
