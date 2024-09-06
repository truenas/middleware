import errno

import pytest

from auto_config import pool_name
from middlewared.service_exception import ValidationError, ValidationErrors
from middlewared.test.integration.utils.client import call


@pytest.fixture(scope="module")
def scrub_info():
    for i in call("pool.scrub.query", [["name", "=", pool_name]]):
        return i
    else:
        # by default, on pool creation a scrub task is created
        assert False, f"Failed to find scrub job for {pool_name!r}"


def test_create_duplicate_scrub_fails(scrub_info):
    with pytest.raises(ValidationErrors) as ve:
        call(
            "pool.scrub.create",
            {
                "pool": scrub_info["pool"],
                "threshold": 1,
                "description": "",
                "schedule": {
                    "minute": "00",
                    "hour": "00",
                    "dom": "1",
                    "month": "1",
                    "dow": "1",
                },
                "enabled": True,
            },
        )
    assert ve.value.errors == [
        ValidationError(
            "pool_scrub_create.pool",
            "A scrub with this pool already exists",
            errno.EINVAL,
        )
    ]


def test_update_scrub(scrub_info):
    assert call(
        "pool.scrub.update",
        scrub_info["id"],
        {
            "threshold": 2,
            "description": "",
            "schedule": {
                "minute": "00",
                "hour": "00",
                "dom": "1",
                "month": "1",
                "dow": "1",
            },
            "enabled": True,
        },
    )


def test_delete_scrub(scrub_info):
    call("pool.scrub.delete", scrub_info["id"])
    assert call("pool.scrub.query", [["name", "=", pool_name]]) == []


def test_create_scrub(scrub_info):
    assert call(
        "pool.scrub.create",
        {
            "pool": scrub_info["pool"],
            "threshold": 1,
            "description": "",
            "schedule": {
                "minute": "00",
                "hour": "00",
                "dom": "1",
                "month": "1",
                "dow": "1",
            },
            "enabled": True,
        },
    )
