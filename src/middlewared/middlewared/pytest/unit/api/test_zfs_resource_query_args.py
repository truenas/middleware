from middlewared.api.current import ZFSResourceQueryArgs, ZFSResourceQueryOptions
from middlewared.api.v26_0_0.zfs_resource_crud import ZFSResourceQuery as ZFSResourceQueryV26


def legacy_value(**data):
    """The shape the version walker hands `from_previous`: a materialised `data` dict plus the new defaults."""
    return {
        "data": ZFSResourceQueryV26(**data).model_dump(),
        "filters": [],
        "options": ZFSResourceQueryOptions(),
    }


def test_from_previous_moves_data_into_extra():
    value = ZFSResourceQueryArgs.from_previous(
        legacy_value(paths=["tank/foo"], properties=["mountpoint"], get_children=True)
    )

    assert "data" not in value
    assert value["filters"] == []
    assert value["options"]["extra"]["paths"] == ["tank/foo"]
    assert value["options"]["extra"]["properties"] == ["mountpoint"]
    assert value["options"]["extra"]["get_children"] is True

    args = ZFSResourceQueryArgs(**value)
    assert args.filters == []
    assert args.options.extra.paths == ["tank/foo"]
    assert args.options.extra.properties == ["mountpoint"]
    assert args.options.extra.get_children is True


def test_from_previous_drops_nest_results():
    value = ZFSResourceQueryArgs.from_previous(legacy_value(nest_results=True))

    assert "nest_results" not in value["options"]["extra"]
    assert ZFSResourceQueryArgs(**value).options.extra.paths == []


def test_from_previous_without_arguments():
    args = ZFSResourceQueryArgs(**ZFSResourceQueryArgs.from_previous(legacy_value()))

    assert args.filters == []
    assert args.options.extra == ZFSResourceQueryArgs().options.extra
