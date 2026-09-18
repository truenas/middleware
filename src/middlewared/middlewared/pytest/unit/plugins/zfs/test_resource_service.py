import pytest

from middlewared.api.base.handler.accept import validate_model
from middlewared.api.current import (
    ZFSResourceEntry,
    ZFSResourceListArgs,
    ZFSResourceListResult,
    ZFSResourceQuery,
    ZFSResourceUpdateArgs,
    ZFSResourceUpdateProperties,
    ZFSResourceUpdateResult,
)
from middlewared.plugins.zfs.resource import ZFSResourceService
from middlewared.service_exception import ValidationErrors


def test_list_carries_typed_models():
    assert ZFSResourceService.list.new_style_accepts is ZFSResourceListArgs
    assert ZFSResourceService.list.new_style_returns is ZFSResourceListResult


def test_update_carries_typed_models():
    assert ZFSResourceService.update.new_style_accepts is ZFSResourceUpdateArgs
    assert ZFSResourceService.update.new_style_returns is ZFSResourceUpdateResult


def test_list_and_create_carry_explicit_roles():
    assert ZFSResourceService.list.roles == ["ZFS_RESOURCE_READ"]
    assert ZFSResourceService.create.roles == ["ZFS_RESOURCE_WRITE"]


def test_update_carries_explicit_write_role():
    # `update` is exempt from the decorator's "roles are required" check, so a
    # missing `roles=` would ship a public mutating method with none.
    assert ZFSResourceService.update.roles == ["ZFS_RESOURCE_WRITE"]


@pytest.mark.parametrize("name", ["casesensitivity", "volblocksize", "normalization", "utf8only", "encryption"])
def test_update_properties_reject_creation_only_names(name):
    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        ZFSResourceUpdateProperties(**{name: "on"})


def test_update_properties_schema_omits_private_and_creation_only_names():
    published = set(ZFSResourceUpdateProperties.model_json_schema()["properties"])
    assert "compression" in published
    assert "volsize" in published
    assert not published & {"casesensitivity", "volblocksize", "normalization", "utf8only", "encryption"}
    assert not published & {"canmount", "mountpoint", "overlay", "prefetch", "primarycache", "secondarycache", "setuid"}


def test_update_rejects_private_property_for_api_callers():
    with pytest.raises(ValidationErrors) as exc_info:
        validate_model(
            ZFSResourceUpdateArgs,
            {"data": {"path": "tank/a", "properties": {"mountpoint": "/mnt/elsewhere"}}},
            allow_private=False,
        )

    assert len(exc_info.value.errors) == 1
    assert exc_info.value.errors[0].attribute == "data.properties.mountpoint"
    assert exc_info.value.errors[0].errmsg == "Extra inputs are not permitted"


@pytest.mark.parametrize("name", ["query", "get_instance", "do_create", "do_delete", "delete"])
def test_crud_methods_are_absent(name):
    assert not hasattr(ZFSResourceService, name)


def test_list_rejects_private_query_field():
    with pytest.raises(ValidationErrors) as exc_info:
        validate_model(ZFSResourceListArgs, {"data": {"exclude_internal_paths": False}}, allow_private=False)

    assert len(exc_info.value.errors) == 1
    assert exc_info.value.errors[0].attribute == "data.exclude_internal_paths"
    assert exc_info.value.errors[0].errmsg == "Extra inputs are not permitted"


def test_list_args_default_construct():
    assert ZFSResourceListArgs().data == ZFSResourceQuery()


def test_query_rejects_negative_max_depth():
    with pytest.raises(ValueError):
        ZFSResourceQuery(max_depth=-1)


def test_entry_field_set():
    fields = set(ZFSResourceEntry.model_fields)
    assert "children" in fields
    assert not fields & {"id", "crypto", "snapshot_count", "snapshots"}
