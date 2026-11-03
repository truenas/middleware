import json

import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.account import group
from middlewared.test.integration.utils import call, ssh

MCP_FIELDS = ("mcp_enabled", "mcp_allowed_groups", "mcp_allow_write")


@pytest.fixture(autouse=True)
def restore_mcp_config():
    config = call("webshare.config")
    try:
        yield
    finally:
        call("webshare.update", {field: config[field] for field in MCP_FIELDS})


def _attributes(payload):
    with pytest.raises(ValidationErrors) as ve:
        call("webshare.update", payload)
    return [error.attribute for error in ve.value.errors]


def test_enable_without_groups_is_rejected():
    assert _attributes({"mcp_enabled": True, "mcp_allowed_groups": []}) == ["mcp_allowed_groups"]


def test_group_without_webshare_access_is_rejected():
    with group({"name": "webshare_mcp_test"}):
        attributes = _attributes({"mcp_enabled": True, "mcp_allowed_groups": ["webshare_mcp_test"]})

    assert attributes == ["mcp_allowed_groups.0"]


def test_nonexistent_group_is_rejected():
    assert _attributes({"mcp_enabled": True, "mcp_allowed_groups": ["webshare_mcp_missing"]}) == [
        "mcp_allowed_groups.0"
    ]


def test_errors_are_reported_across_fields():
    attributes = _attributes(
        {"bindip": ["192.0.2.1"], "mcp_enabled": True, "mcp_allowed_groups": ["webshare_mcp_missing"]}
    )

    assert set(attributes) == {"bindip.0", "mcp_allowed_groups.0"}


def test_webshare_group_is_accepted_and_rendered():
    call(
        "webshare.update",
        {"mcp_enabled": True, "mcp_allowed_groups": ["truenas_webshare"], "mcp_allow_write": True},
    )

    config = call("webshare.config")
    assert config["mcp_enabled"] is True
    assert config["mcp_allowed_groups"] == ["truenas_webshare"]
    assert config["mcp_allow_write"] is True

    call("etc.generate", "webshare")
    rendered = json.loads(ssh("cat /etc/webshare-auth/config.json"))
    assert rendered["mcp"] == {
        "enabled": True,
        "allowed_groups": ["truenas_webshare"],
        "allow_write": True,
    }
