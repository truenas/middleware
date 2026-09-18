import pytest

from middlewared.api.current import ZFSResourceQuery
from middlewared.plugins.zfs.resource_query import nest_paths, validate_query_args
from middlewared.service_exception import ValidationError


def node(name, children=None):
    return {"name": name, "pool": name.split("/")[0], "children": children}


def test_nest_paths_hierarchical():
    rows = [node("tank", []), node("tank/a", []), node("tank/a/b", [])]
    roots = nest_paths(rows)

    assert [r["name"] for r in roots] == ["tank"]
    assert [c["name"] for c in roots[0]["children"]] == ["tank/a"]
    assert [c["name"] for c in roots[0]["children"][0]["children"]] == ["tank/a/b"]


def test_nest_paths_out_of_order():
    rows = [node("tank/a/b", []), node("tank", []), node("tank/a", [])]
    roots = nest_paths(rows)

    assert [r["name"] for r in roots] == ["tank"]
    assert [c["name"] for c in roots[0]["children"]] == ["tank/a"]
    assert [c["name"] for c in roots[0]["children"][0]["children"]] == ["tank/a/b"]


def test_nest_paths_ancestor_without_children_list():
    rows = [node("tank"), node("tank/a")]
    roots = nest_paths(rows)

    assert [r["name"] for r in roots] == ["tank"]
    assert [c["name"] for c in roots[0]["children"]] == ["tank/a"]


def test_nest_paths_skips_missing_intermediate():
    rows = [node("tank", []), node("tank/a/b")]
    roots = nest_paths(rows)

    assert [c["name"] for c in roots[0]["children"]] == ["tank/a/b"]


def test_nest_paths_orphan_becomes_root():
    rows = [node("tank/a"), node("tank/a/b")]
    roots = nest_paths(rows)

    assert [r["name"] for r in roots] == ["tank/a"]
    assert [c["name"] for c in roots[0]["children"]] == ["tank/a/b"]


def test_validate_rejects_snapshot_path():
    with pytest.raises(ValidationError) as exc_info:
        validate_query_args(ZFSResourceQuery(paths=["tank/a@snap"]))
    assert exc_info.value.attribute == "zfs.resource.list"


@pytest.mark.parametrize("kwargs", [{"get_children": True}, {"max_depth": 1}])
def test_validate_rejects_overlap_when_descending(kwargs):
    with pytest.raises(ValidationError) as exc_info:
        validate_query_args(ZFSResourceQuery(paths=["tank/a", "tank/a/b"], **kwargs))
    assert "overlapping" in exc_info.value.errmsg.lower()


def test_validate_accepts_overlap_without_descent():
    validate_query_args(ZFSResourceQuery(paths=["tank/a", "tank/a/b"], max_depth=0))
