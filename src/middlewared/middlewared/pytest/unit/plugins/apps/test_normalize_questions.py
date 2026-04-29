import logging
from unittest.mock import AsyncMock, patch

import pytest

from middlewared.plugins.apps.schema_normalization import normalize_question
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service import ServiceContext


@pytest.mark.parametrize("attr_schema, value, update", [
    (
        {
            "variable": "cert_id",
            "schema": {
                "type": "int",
                "$ref": ["definitions/certificate"]
            }
        },
        1234,
        False
    ),
    (
        {
            "variable": "acl_config",
            "schema": {
                "type": "dict",
                "$ref": ["normalize/acl"],
                "attrs": []
            }
        },
        {"entries": [], "path": "/mnt/data"},
        False
    ),
    (
        {
            "variable": "acl_config",
            "schema": {
                "type": "dict",
                "$ref": ["normalize/acl"],
                "attrs": []
            }
        },
        {"entries": [], "path": "/mnt/data"},
        True
    ),
    (
        {
            "variable": "cert_id",
            "schema": {
                "type": "int",
                "null": True,
                "$ref": ["definitions/certificate"]
            }
        },
        None,
        False
    )
])
@patch("middlewared.plugins.apps.schema_normalization.normalize_certificate", new_callable=AsyncMock)
@patch("middlewared.plugins.apps.schema_normalization.normalize_acl", new_callable=AsyncMock)
@patch("middlewared.plugins.apps.schema_normalization.normalize_ix_volume", new_callable=AsyncMock)
@patch("middlewared.plugins.apps.schema_normalization.normalize_gpu_configuration", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_normalize_question(mock_gpu, mock_vol, mock_acl, mock_cert, attr_schema, value, update):
    for mock in (mock_gpu, mock_vol, mock_acl, mock_cert):
        mock.return_value = value
    ctx = ServiceContext(Middleware(), logging.getLogger("test"))
    result = await normalize_question(ctx, attr_schema, value, update, {}, {})
    assert result == value


@pytest.mark.parametrize("attr_schema, value, update", [
    (
        {
            "variable": "cert_list",
            "schema": {
                "type": "list",
                "$ref": ["definitions/certificate"],
                "items": [
                    {
                        "variable": "cert_item",
                        "schema": {
                            "type": "int",
                            "$ref": ["definitions/certificate"]
                        }
                    }
                ]
            }
        },
        [1, 2, 3],
        False
    ),
])
@patch("middlewared.plugins.apps.schema_normalization.normalize_certificate", new_callable=AsyncMock)
@patch("middlewared.plugins.apps.schema_normalization.normalize_acl", new_callable=AsyncMock)
@patch("middlewared.plugins.apps.schema_normalization.normalize_ix_volume", new_callable=AsyncMock)
@patch("middlewared.plugins.apps.schema_normalization.normalize_gpu_configuration", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_normalize_question_List(mock_gpu, mock_vol, mock_acl, mock_cert, attr_schema, value, update):
    # Mock the normalize functions to return the value parameter as-is
    for mock in (mock_gpu, mock_vol, mock_acl, mock_cert):
        mock.side_effect = lambda ctx, attr, val, config, norm_ctx: val

    ctx = ServiceContext(Middleware(), logging.getLogger("test"))
    result = await normalize_question(ctx, attr_schema, value, update, {}, {})
    assert result == value


@pytest.mark.parametrize("attr_schema, value, update", [
    (
        {
            "variable": "storage_config",
            "schema": {
                "type": "dict",
                "attrs": [
                    {
                        "variable": "volume",
                        "schema": {
                            "type": "dict",
                            "$ref": ["normalize/ix_volume"]
                        }
                    },
                    {
                        "variable": "certificate",
                        "schema": {
                            "type": "int",
                            "$ref": ["definitions/certificate"]
                        }
                    }
                ]
            }
        },
        {
            "volume": {"dataset_name": "mydata", "properties": {}},
            "certificate": 123
        },
        False
    ),
])
@patch("middlewared.plugins.apps.schema_normalization.normalize_certificate", new_callable=AsyncMock)
@patch("middlewared.plugins.apps.schema_normalization.normalize_acl", new_callable=AsyncMock)
@patch("middlewared.plugins.apps.schema_normalization.normalize_ix_volume", new_callable=AsyncMock)
@patch("middlewared.plugins.apps.schema_normalization.normalize_gpu_configuration", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_normalize_nested_dict_with_refs(mock_gpu, mock_vol, mock_acl, mock_cert, attr_schema, value, update):
    async def mock_normalize_ix_volume(ctx, attr, val, config, norm_ctx):
        config["ix_volumes"][val["dataset_name"]] = {"path": f'/mnt/ix-apps/{val["dataset_name"]}'}
        return val

    async def mock_normalize_certificate(ctx, attr, val, config, norm_ctx):
        config["ix_certificates"][val] = {"name": f"cert-{val}"}
        return val

    mock_vol.side_effect = mock_normalize_ix_volume
    mock_cert.side_effect = mock_normalize_certificate

    complete_config = {
        "ix_volumes": {},
        "ix_certificates": {}
    }
    normalization_context = {"actions": []}

    ctx = ServiceContext(Middleware(), logging.getLogger("test"))
    result = await normalize_question(ctx, attr_schema, value, update, complete_config, normalization_context)

    # Check that the normalization was applied
    assert result == value
    assert "mydata" in complete_config["ix_volumes"]
    assert 123 in complete_config["ix_certificates"]
