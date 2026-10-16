import pytest

from middlewared.api.base.handler.accept import validate_model
from middlewared.api.base.handler.version import APIVersion, APIVersionsAdapter
from middlewared.api.v27_0_0.zfs_resource_snapshot import (
    ZFSResourceSnapshotCloneArgs as ZFSResourceSnapshotCloneArgs_v27_0_0,
)
from middlewared.api.v27_0_0.zfs_resource_snapshot import (
    ZFSResourceSnapshotRenameArgs as ZFSResourceSnapshotRenameArgs_v27_0_0,
)
from middlewared.api.v28_0_0.zfs_resource_snapshot import (
    ZFSResourceSnapshotCloneArgs as ZFSResourceSnapshotCloneArgs_v28_0_0,
)
from middlewared.api.v28_0_0.zfs_resource_snapshot import (
    ZFSResourceSnapshotRenameArgs as ZFSResourceSnapshotRenameArgs_v28_0_0,
)

from .utils import TestModelProvider


def _build_adapter():
    return APIVersionsAdapter(
        [
            APIVersion(
                "v27.0.0",
                TestModelProvider(
                    {
                        "ZFSResourceSnapshotRenameArgs": ZFSResourceSnapshotRenameArgs_v27_0_0,
                        "ZFSResourceSnapshotCloneArgs": ZFSResourceSnapshotCloneArgs_v27_0_0,
                    }
                ),
            ),
            APIVersion(
                "v28.0.0",
                TestModelProvider(
                    {
                        "ZFSResourceSnapshotRenameArgs": ZFSResourceSnapshotRenameArgs_v28_0_0,
                        "ZFSResourceSnapshotCloneArgs": ZFSResourceSnapshotCloneArgs_v28_0_0,
                    }
                ),
            ),
        ]
    )


@pytest.mark.asyncio
async def test_rename_from_v27_is_forced():
    adapter = _build_adapter()
    value = {"data": {"current_name": "tank/ds@a", "new_name": "tank/ds@b"}}

    result = await adapter.adapt(value, "ZFSResourceSnapshotRenameArgs", "v27.0.0", "v28.0.0")

    assert result["data"]["force"] is True
    validate_model(ZFSResourceSnapshotRenameArgs_v28_0_0, result)


@pytest.mark.asyncio
async def test_clone_from_v27_splits_user_properties():
    adapter = _build_adapter()
    value = {
        "data": {
            "snapshot": "tank/ds@a",
            "dataset": "tank/clone",
            "properties": {"compression": "lz4", "org.truenas:tag": 1},
        }
    }

    result = await adapter.adapt(value, "ZFSResourceSnapshotCloneArgs", "v27.0.0", "v28.0.0")

    assert result["data"]["properties"] == {"compression": "lz4"}
    assert result["data"]["user_properties"] == {"org.truenas:tag": "1"}
    validate_model(ZFSResourceSnapshotCloneArgs_v28_0_0, result)
