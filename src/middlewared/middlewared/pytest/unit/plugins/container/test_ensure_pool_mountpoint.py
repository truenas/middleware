import errno
from unittest.mock import AsyncMock, Mock

import pytest

from middlewared.plugins.container.dataset import ContainerService
from middlewared.pytest.unit.helpers import create_service
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service_exception import CallError


POOL = "tank"
DATASET = f"{POOL}/.truenas_containers"
# The property is stored without the pool's /mnt altroot; ZFS reports it back with.
EXPECTED_PROP = f"/.truenas_containers/{POOL}"
EXPECTED_PATH = f"/mnt{EXPECTED_PROP}"
DRIFTED_PATH = f"/mnt/{POOL}/.truenas_containers"


def resource(mountpoint):
    return {
        "name": DATASET,
        "type": "FILESYSTEM",
        "properties": {"mountpoint": {"value": mountpoint}},
    }


def make_service(*, resources, statfs=None):
    m = Middleware()
    m.services.zfs.resource.query_impl = Mock(return_value=resources)
    if isinstance(statfs, Exception):
        m["filesystem.statfs"] = AsyncMock(side_effect=statfs)
    else:
        m["filesystem.statfs"] = AsyncMock(return_value=statfs)
    m["pool.dataset.update_impl"] = AsyncMock()
    return create_service(m, ContainerService), m


@pytest.mark.asyncio
async def test_noop_when_dataset_absent():
    svc, m = make_service(resources=[])

    assert await svc.ensure_pool_mountpoint(POOL) is False
    m["pool.dataset.update_impl"].assert_not_called()


@pytest.mark.asyncio
async def test_noop_when_mountpoint_correct():
    svc, m = make_service(resources=[resource(EXPECTED_PATH)])

    assert await svc.ensure_pool_mountpoint(POOL) is False
    m["pool.dataset.update_impl"].assert_not_called()
    m["filesystem.statfs"].assert_not_called()


@pytest.mark.asyncio
async def test_repairs_drifted_mountpoint():
    svc, m = make_service(
        resources=[resource(DRIFTED_PATH)],
        statfs=CallError("Path not found.", errno.ENOENT),
    )

    assert await svc.ensure_pool_mountpoint(POOL) is True
    m["pool.dataset.update_impl"].assert_called_once_with({"name": DATASET, "zprops": {"mountpoint": EXPECTED_PROP}})


@pytest.mark.asyncio
async def test_repairs_when_expected_path_is_not_a_mount_root():
    # statfs described the filesystem *containing* the path, not a mount at it.
    svc, m = make_service(
        resources=[resource(DRIFTED_PATH)],
        statfs={"dest": "/mnt", "source": POOL},
    )

    assert await svc.ensure_pool_mountpoint(POOL) is True
    m["pool.dataset.update_impl"].assert_called_once()


@pytest.mark.asyncio
async def test_repairs_when_already_mounted_by_us():
    svc, m = make_service(
        resources=[resource(DRIFTED_PATH)],
        statfs={"dest": EXPECTED_PATH, "source": DATASET},
    )

    assert await svc.ensure_pool_mountpoint(POOL) is True
    m["pool.dataset.update_impl"].assert_called_once()


@pytest.mark.asyncio
async def test_refuses_to_overmount_foreign_dataset():
    svc, m = make_service(
        resources=[resource(DRIFTED_PATH)],
        statfs={"dest": EXPECTED_PATH, "source": "dozer/.truenas_containers"},
    )

    assert await svc.ensure_pool_mountpoint(POOL) is False
    m["pool.dataset.update_impl"].assert_not_called()


@pytest.mark.asyncio
async def test_statfs_error_other_than_enoent_propagates():
    svc, m = make_service(
        resources=[resource(DRIFTED_PATH)],
        statfs=CallError("Permission denied.", errno.EACCES),
    )

    with pytest.raises(CallError):
        await svc.ensure_pool_mountpoint(POOL)

    m["pool.dataset.update_impl"].assert_not_called()


@pytest.mark.asyncio
async def test_queries_by_explicit_container_path():
    # The container dataset is an internal path, so query_impl only returns it when it is named
    # explicitly. Querying the pool instead would silently disable the whole repair.
    svc, m = make_service(resources=[resource(EXPECTED_PATH)])

    await svc.ensure_pool_mountpoint(POOL)

    query = m.services.zfs.resource.query_impl.call_args.args[0]
    assert query.paths == [DATASET]
