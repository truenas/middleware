import pytest

from middlewared.api.base.handler.accept import validate_model
from middlewared.api.base.handler.version import APIVersion, APIVersionsAdapter
from middlewared.api.v27_0_0.app import AppUpgradeArgs as AppUpgradeArgs_v27_0_0
from middlewared.api.v27_0_0.app import AppUpgradeBulkArgs as AppUpgradeBulkArgs_v27_0_0
from middlewared.api.v28_0_0.app import AppUpgradeArgs as AppUpgradeArgs_v28_0_0
from middlewared.api.v28_0_0.app import AppUpgradeBulkArgs as AppUpgradeBulkArgs_v28_0_0

from .utils import TestModelProvider


def _build_adapter():
    return APIVersionsAdapter(
        [
            APIVersion(
                "v27.0.0",
                TestModelProvider(
                    {
                        "AppUpgradeArgs": AppUpgradeArgs_v27_0_0,
                        "AppUpgradeBulkArgs": AppUpgradeBulkArgs_v27_0_0,
                    }
                ),
            ),
            APIVersion(
                "v28.0.0",
                TestModelProvider(
                    {
                        "AppUpgradeArgs": AppUpgradeArgs_v28_0_0,
                        "AppUpgradeBulkArgs": AppUpgradeBulkArgs_v28_0_0,
                    }
                ),
            ),
        ]
    )


@pytest.mark.asyncio
async def test_upgrade_from_v27_is_forced():
    adapter = _build_adapter()
    value = {"app_name": "plex", "options": {"values": {"storage": {"data": {"type": "host_path"}}}}}

    result = await adapter.adapt(value, "AppUpgradeArgs", "v27.0.0", "v28.0.0")

    assert result["options"]["force_path_conflicts"] is True
    assert result["options"]["values"] == {"storage": {"data": {"type": "host_path"}}}
    validate_model(AppUpgradeArgs_v28_0_0, result)


@pytest.mark.asyncio
async def test_upgrade_from_v27_without_options_is_forced():
    adapter = _build_adapter()

    result = await adapter.adapt({"app_name": "plex"}, "AppUpgradeArgs", "v27.0.0", "v28.0.0")

    assert result["options"]["force_path_conflicts"] is True
    validate_model(AppUpgradeArgs_v28_0_0, result)


@pytest.mark.asyncio
async def test_bulk_upgrade_from_v27_is_forced():
    adapter = _build_adapter()
    value = {"apps": [{"app_name": "plex", "options": {"values": {"x": 1}}}, {"app_name": "sonarr"}]}

    result = await adapter.adapt(value, "AppUpgradeBulkArgs", "v27.0.0", "v28.0.0")

    assert [entry["options"]["force_path_conflicts"] for entry in result["apps"]] == [True, True]
    assert result["apps"][0]["options"]["values"] == {"x": 1}
    validate_model(AppUpgradeBulkArgs_v28_0_0, result)
