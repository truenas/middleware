from middlewared.plugins.zfs.resource_query import nest_paths


def node(name, children=None):
    return {"name": name, "pool": name.split("/")[0], "children": children}


def test_nest_paths_skips_missing_intermediate():
    rows = [node("tank", []), node("tank/a/b")]
    roots = nest_paths(rows)

    assert [c["name"] for c in roots[0]["children"]] == ["tank/a/b"]
