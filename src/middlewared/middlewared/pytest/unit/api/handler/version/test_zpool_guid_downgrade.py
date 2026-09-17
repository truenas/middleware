"""v27 reports pool and vdev guids as decimal strings; v26 clients get the integers back."""

import pytest

from middlewared.api.base.handler.version import APIVersion, APIVersionsAdapter
from middlewared.api.v26_0_0.zpool_query import ZPoolQueryResult as ZPoolQueryResult_v26_0_0
from middlewared.api.v27_0_0.zpool import ZPoolQueryResult as ZPoolQueryResult_v27_0_0

from .utils import TestModelProvider

MODEL_NAME = "ZPoolQueryResult"
# above 2**53, which is where a JSON consumer reading a number as a double starts rounding
POOL_GUID = 13849128093487261283
VDEV_GUID = 17303962713598463910
LEAF_GUID = 9223372036854775809


def _build_adapter():
    return APIVersionsAdapter(
        [
            APIVersion("v26.0.0", TestModelProvider({MODEL_NAME: ZPoolQueryResult_v26_0_0})),
            APIVersion("v27.0.0", TestModelProvider({MODEL_NAME: ZPoolQueryResult_v27_0_0})),
        ]
    )


def vdev(guid, top_guid=None, children=()):
    return {
        "name": "mirror-0",
        "vdev_type": "mirror",
        "guid": str(guid),
        "state": "ONLINE",
        "stats": {},
        "children": list(children),
        "top_guid": None if top_guid is None else str(top_guid),
        "path": None,
    }


def entry(**overrides):
    return {
        "id": 1,
        "name": "tank",
        "guid": str(POOL_GUID),
        "status": "ONLINE",
        "healthy": True,
        "warning": False,
        "status_code": "OK",
        "status_detail": None,
        "is_upgraded": True,
        "all_sed": False,
        "properties": None,
        "topology": None,
        "scan": None,
        "expand": None,
        "features": None,
    } | overrides


async def adapt(entries):
    return (await _build_adapter().adapt({"result": entries}, MODEL_NAME, "v27.0.0", "v26.0.0"))["result"]


@pytest.mark.asyncio
async def test_pool_guid_is_an_integer_again():
    result = await adapt([entry()])
    assert result[0]["guid"] == POOL_GUID
    assert isinstance(result[0]["guid"], int)


@pytest.mark.asyncio
async def test_vdev_guids_are_integers_at_every_depth():
    topology = {
        "data": [vdev(VDEV_GUID, children=[vdev(LEAF_GUID, top_guid=VDEV_GUID)])],
        "log": [],
        "cache": [],
        "spares": [],
        "special": [],
        "dedup": [],
    }
    result = await adapt([entry(topology=topology)])
    top = result[0]["topology"]["data"][0]
    assert top["guid"] == VDEV_GUID
    assert top["children"][0]["guid"] == LEAF_GUID
    assert top["children"][0]["top_guid"] == VDEV_GUID


@pytest.mark.asyncio
async def test_offline_entry_placeholder_guid():
    result = await adapt([entry(id=None, guid="0", status="OFFLINE", healthy=False, is_upgraded=None)])
    assert result[0]["guid"] == 0
