import logging

import pytest

from middlewared.plugins.apps.schema_normalization import normalize_ix_volume
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service import ServiceContext


@pytest.mark.parametrize("attr, value, complete_config, normalization_context", [
    (
        {"schema": {"type": "dict"}},
        {
            "dataset_name": "volume_1",
            "properties": {"prop_key": "prop_value"},
            "acl_entries": {
                "entries": [{"type": "ALLOW", "permissions": "write"}],
                "path": "/mnt/data"
            }
        },
        {
            "ix_volumes": {
                "volume_1": ""
            }
        },
        {"actions": [], "app": {"name": "test_app"}}
    ),
    (
        {"schema": {"type": "dict"}},
        {
            "dataset_name": "volume_1",
            "properties": {"prop_key": "prop_value"},
            "acl_entries": {
                "entries": [],
                "path": ""
            }
        },
        {
            "ix_volumes": {
                "volume_1": ""
            }
        },
        {"actions": [], "app": {"name": "test_app"}}
    ),
    (
        {"schema": {"type": "dict"}},
        {
            "dataset_name": "volume_1",
            "properties": {"prop_key": "prop_value"},
            "acl_entries": {
                "entries": [],
                "path": ""
            }

        },
        {
            "ix_volumes": {
                "volume_1": ""
            }
        },
        {
            "actions": [
                {
                    "method": "update_volumes",
                    "args": ["test_app", [
                        {
                            "name": "volume_1"
                        }
                    ]]
                }
            ],
            "app": {"name": "test_app"}
        }
    ),
    (
        {"schema": {"type": "dict"}},
        {
            "dataset_name": "volume_1",
            "properties": {"prop_key": "prop_value"},
            "acl_entries": {
                "entries": [],
                "path": ""
            }

        },
        {
            "ix_volumes": {
                "volume_1": ""
            }
        },
        {
            "actions": [
                {
                    "method": "update_volumes",
                    "args": ["test_app", [
                        {
                            "name": "volume_2"
                        }
                    ]]
                }
            ],
            "app": {"name": "test_app"}
        }
    ),
])
@pytest.mark.asyncio
async def test_normalize_ix_volumes(attr, value, complete_config, normalization_context):
    ctx = ServiceContext(Middleware(), logging.getLogger("test"))
    result = await normalize_ix_volume(ctx, attr, value, complete_config, normalization_context)
    assert len(normalization_context["actions"]) > 0
    assert value["dataset_name"] in [v["name"] for v in normalization_context["actions"][0]["args"][-1]]
    assert result == value
