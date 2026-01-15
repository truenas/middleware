from unittest.mock import AsyncMock, Mock

import pytest

from middlewared.plugins.truesearch import TrueSearchService


@pytest.mark.asyncio
@pytest.mark.parametrize("directories,datasets,result", [
    ({"/mnt/tank/users"}, {"tank": False}, ["/mnt/tank/users"]),
    ({"/mnt/tank/users/alex"}, {"tank": False, "tank/users": False}, ["/mnt/tank/users/alex"]),
    ({"/mnt/tank/users"}, {"tank": False, "tank/users": True}, []),
    ({"/mnt/tank/users/alex"}, {"tank": False, "tank/users": True}, []),
    ({"/mnt/tank/users"},
     {"tank": False, "tank/users": False, "tank/users/alice": False, "tank/users/bob": False,
      "tank/users/alice/books": False, "tank/users/alice/documents": True},
     ["/mnt/tank/users", "/mnt/tank/users/alice", "/mnt/tank/users/alice/books", "/mnt/tank/users/bob"]),
])
async def test_process_directories(directories, datasets, result):
    middleware = Mock()
    middleware.call2 = AsyncMock(return_value=[
        {
            "type": "FILESYSTEM",
            "properties": {
                "mountpoint": {
                    "value": f"/mnt/{dataset}"
                },
                "encryption": {
                    "value": "on" if encrypted else "off"
                },
            }
        }
        for dataset, encrypted in datasets.items()
    ])
    assert await TrueSearchService(middleware).process_directories(directories) == result


@pytest.mark.asyncio
async def test_legacy_mountpoint():
    middleware = Mock()
    middleware.call2 = AsyncMock(return_value=[
        {
            "type": "FILESYSTEM",
            "properties": {
                "mountpoint": {
                    "value": "legacy"
                },
                "encryption": {
                    "value": "off"
                },
            }
        },
        {
            "type": "FILESYSTEM",
            "properties": {
                "mountpoint": {
                    "value": "/mnt/tank/users"
                },
                "encryption": {
                    "value": "off"
                },
            }
        },
    ])
    assert await TrueSearchService(middleware).process_directories({"/mnt/tank/users"}) == ["/mnt/tank/users"]
