from middlewared.plugins.webui.dataset_consumers import DatasetIndex, match_iscsi, match_push_tasks, match_smb


def filesystem(name, mountpoint=None):
    return {
        "name": name,
        "type": "FILESYSTEM",
        "properties": {"mountpoint": {"raw": mountpoint or f"/mnt/{name}"}},
    }


def volume(name):
    return {"name": name, "type": "VOLUME", "properties": {}}


def no_resolve(path):
    raise AssertionError(f"{path} should not need the kernel")


def test_iscsi_extent_mapped_to_two_targets_is_listed_once():
    index = DatasetIndex([filesystem("tank"), filesystem("tank/a"), filesystem("tank/a/b")])
    extents = [
        {"id": 3, "type": "FILE", "path": "/mnt/tank/a/b/x.img", "dataset": "tank/a/b", "enabled": True},
        {"id": 4, "type": "FILE", "path": "/mnt/tank/a/y.img", "dataset": "tank/a", "enabled": True},
    ]
    targets = [{"id": 1, "groups": [{"portal": 1}]}, {"id": 2, "groups": [{"portal": 1}]}, {"id": 5, "groups": []}]
    targetextents = [{"target": 1, "extent": 3}, {"target": 2, "extent": 3}, {"target": 5, "extent": 4}]

    result = match_iscsi(index, extents, targets, targetextents, no_resolve)

    assert list(result) == ["tank/a/b"]
    assert [item.path for item in result["tank/a/b"]] == ["/mnt/tank/a/b/x.img"]


def test_locked_child_share_belongs_to_child_only():
    index = DatasetIndex([filesystem("tank"), filesystem("tank/enc"), filesystem("tank/enc/locked")])
    resolved = []

    def resolve(path):
        resolved.append(path)
        return "tank/enc"

    shares = [{"path": "/mnt/tank/enc/locked/", "dataset": "tank/enc", "enabled": True, "name": "locked"}]

    result = match_smb(index, shares, resolve)

    assert list(result) == ["tank/enc/locked"]
    assert resolved == []


def test_push_tasks_count_ancestors_only():
    index = DatasetIndex(
        [
            filesystem("tank"),
            filesystem("tank/a"),
            filesystem("tank/a/b"),
            filesystem("tank/ab"),
            volume("tank/a/vol"),
            filesystem("tank/nomnt", "none"),
        ]
    )
    tasks = [
        {"direction": "PUSH", "path": "/mnt/tank/a"},
        {"direction": "PULL", "path": "/mnt/tank"},
        {"direction": "PUSH", "path": "/mnt/tank/a/"},
    ]

    result = match_push_tasks(index, tasks)

    assert {name: result.get(name, 0) for name in index.types} == {
        "tank": 0,
        "tank/a": 2,
        "tank/a/b": 2,
        "tank/ab": 0,
        "tank/a/vol": 0,
        "tank/nomnt": 0,
    }
