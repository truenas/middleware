import logging

import pytest

from middlewared.plugins.apps.schema_normalization import normalize_values
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service import ServiceContext


@pytest.mark.parametrize("dict_attrs, values, update, normalization_context, expected", [
    (
        # Empty questions list - just reserved names
        [],
        {
            "ix_certificates": {},
            "ix_certificate_authorities": {},
            "ix_volumes": {},
            "ix_context": {}
        },
        False,
        {"app": {"name": "app", "path": "/path/to/app"}, "actions": []},
        (
            {
                "ix_certificates": {},
                "ix_certificate_authorities": {},
                "ix_volumes": {},
                "ix_context": {}
            },
            {
                "app": {
                    "name": "app",
                    "path": "/path/to/app"
                },
                "actions": []
            }
        )
    ),
    (
        # Empty questions list - just reserved names (update mode)
        [],
        {
            "ix_certificates": {},
            "ix_certificate_authorities": {},
            "ix_volumes": {},
            "ix_context": {}
        },
        True,
        {"app": {"name": "app", "path": "/path/to/app"}, "actions": []},
        (
            {
                "ix_certificates": {},
                "ix_certificate_authorities": {},
                "ix_volumes": {},
                "ix_context": {}
            },
            {
                "app": {
                    "name": "app",
                    "path": "/path/to/app"
                },
                "actions": []
            }
        )
    ),
])
@pytest.mark.asyncio
async def test_normalize_values(dict_attrs, values, update, normalization_context, expected):
    ctx = ServiceContext(Middleware(), logging.getLogger("test"))
    result = await normalize_values(
        ctx,
        dict_attrs,
        values,
        update,
        normalization_context
    )
    assert result == expected
