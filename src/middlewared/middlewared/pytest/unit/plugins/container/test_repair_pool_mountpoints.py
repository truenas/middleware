from unittest.mock import AsyncMock

import pytest

from middlewared.plugins.container.lifecycle import ContainerService
from middlewared.pytest.unit.helpers import create_service
from middlewared.pytest.unit.middleware import Middleware


def container(dataset, id_=1):
    return {"id": id_, "name": f"c{id_}", "dataset": dataset}


def make_service(containers, ensure_side_effect=None):
    m = Middleware()
    m["container.query"] = AsyncMock(return_value=containers)
    m["container.ensure_pool_mountpoint"] = AsyncMock(side_effect=ensure_side_effect)
    return create_service(m, ContainerService), m


def repaired_pools(m):
    return [call.args[0] for call in m["container.ensure_pool_mountpoint"].call_args_list]


@pytest.mark.asyncio
async def test_derives_distinct_pools():
    svc, m = make_service(
        [
            container("tank/.truenas_containers/containers/a", 1),
            container("tank/.truenas_containers/containers/b", 2),
            container("dozer/.truenas_containers/containers/c", 3),
        ]
    )

    await svc.repair_pool_mountpoints()

    assert repaired_pools(m) == ["dozer", "tank"]


@pytest.mark.asyncio
async def test_one_pool_failure_does_not_stop_the_rest():
    svc, m = make_service(
        [
            container("dozer/.truenas_containers/containers/a", 1),
            container("tank/.truenas_containers/containers/b", 2),
        ],
        ensure_side_effect=[Exception("boom"), None],
    )

    await svc.repair_pool_mountpoints()

    assert repaired_pools(m) == ["dozer", "tank"]


@pytest.mark.asyncio
async def test_no_containers_is_a_noop():
    svc, m = make_service([])

    await svc.repair_pool_mountpoints()

    m["container.ensure_pool_mountpoint"].assert_not_called()
