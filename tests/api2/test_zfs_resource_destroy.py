import string

from auto_config import pool_name
from middlewared.test.integration.utils import call, ssh


A, B, C = string.ascii_lowercase[:3]
AA, BB, CC = tuple(i * 2 for i in (A, B, C))
AAA, BBB, CCC = tuple(i * 3 for i in (A, B, C))
SNAP1 = "snap1"
SNAP2 = "snap2"
SNAP3 = "snap3"


def create_datasets(create_snaps=False):
    path1 = "/".join([A, B, C])
    path2 = "/".join([AA, BB, CC])
    path3 = "/".join([AAA, BBB, CCC])
    ssh(f"zfs create -p {pool_name}/{path1}")
    ssh(f"zfs create -p {pool_name}/{path2}")
    ssh(f"zfs create -p {pool_name}/{path3}")
    if create_snaps:
        ssh(f"zfs snapshot -r {pool_name}/{A}@{SNAP1}")
        ssh(f"zfs snapshot -r {pool_name}/{A}@{SNAP2}")
        ssh(f"zfs snapshot -r {pool_name}/{A}@{SNAP3}")
        ssh(f"zfs snapshot -r {pool_name}/{AA}@{SNAP1}")
        ssh(f"zfs snapshot -r {pool_name}/{AA}@{SNAP2}")
        ssh(f"zfs snapshot -r {pool_name}/{AA}@{SNAP3}")
        ssh(f"zfs snapshot -r {pool_name}/{AAA}@{SNAP1}")
        ssh(f"zfs snapshot -r {pool_name}/{AAA}@{SNAP2}")
        ssh(f"zfs snapshot -r {pool_name}/{AAA}@{SNAP3}")


def test_destroy_resources():
    create_datasets()

    # Destroy single filesystem
    path = f"{pool_name}/{A}/{B}/{C}"
    rv = call("zfs.resource.destroy", {"paths": [path]})
    assert rv[path] is None
    rv = call(
        "zfs.resource.query",
        {
            "paths": [path],
            "properties": None,
        },
    )
    assert not rv

    # Destroy multiple
    path2 = f"{pool_name}/{AA}/{BB}/{CC}"
    path3 = f"{pool_name}/{AAA}/{BBB}/{CCC}"
    rv = call("zfs.resource.destroy", {"paths": [path2, path3]})
    assert rv[path2] is None
    assert rv[path3] is None
    rv = call(
        "zfs.resource.query",
        {
            "paths": [path2, path3],
            "properties": None,
        },
    )
    assert not rv

    # Destroy single root filesystem recursively
    path1 = f"{pool_name}/{A}"
    rv = call("zfs.resource.destroy", {"paths": [path1], "recursive": True})
    assert rv[path1] is None
    rv = call(
        "zfs.resource.query",
        {
            "paths": [path1],
            "properties": None,
            "get_children": True,
        },
    )
    assert not rv

    # Destroy multiple root filesystem recursively
    path2 = f"{pool_name}/{AA}"
    path3 = f"{pool_name}/{AAA}"
    rv = call(
        "zfs.resource.destroy",
        {
            "paths": [path2, path3],
            "recursive": True
        }
    )
    assert rv[path2] is None
    assert rv[path3] is None
    rv = call(
        "zfs.resource.query",
        {
            "paths": [path2, path3],
            "properties": None,
            "get_children": True,
        },
    )
    assert not rv


def test_destroy_snapshots():
    create_datasets(create_snaps=True)

    # Destroy single snapshot
    snap_src = f"{pool_name}/{A}/{B}/{C}"
    snap_name = f"{snap_src}@{SNAP1}"
    rv = call("zfs.resource.destroy", {"paths": [snap_name]})
    assert rv[snap_name] is None
    rv = call(
        "zfs.resource.query",
        {"paths": [snap_src], "properties": None, "get_snapshots": True},
    )
    assert rv and snap_name not in rv[0]["snapshots"]

    # Destroy multiple snapshots
    snap_src = f"{pool_name}/{A}/{B}/{C}"
    snap_name2 = f"{snap_src}@{SNAP2}"
    snap_name3 = f"{snap_src}@{SNAP3}"
    rv = call("zfs.resource.destroy", {"paths": [snap_name2, snap_name3]})
    assert rv[snap_name2] is None
    assert rv[snap_name3] is None
    rv = call(
        "zfs.resource.query",
        {"paths": [snap_src], "properties": None, "get_snapshots": True},
    )
    assert rv
    assert snap_name2 not in rv[0]["snapshots"]
    assert snap_name3 not in rv[0]["snapshots"]

    # Destroy all SNAP1 named snapshots recursively starting at pool/AA
    snap_src = f"{pool_name}/{AA}"
    snap_name = f"{snap_src}/{SNAP1}"
    rv = call("zfs.resource.destroy", {"paths": [snap_name], "recursive": True})
    assert rv[snap_name] is None
    rv = call(
        "zfs.resource.query",
        {
            "paths": [snap_src],
            "properties": None,
            "get_children": True,
            "get_snapshots": True,
        },
    )
    assert rv
    for i in rv:
        assert f"{snap_src}/{SNAP2}" in i["snapshots"]
        assert f"{snap_src}/{SNAP3}" in i["snapshots"]
        assert snap_name not in i["snapshots"]

    # Destroy multiple snapshots recursive
    snap_src1 = f"{pool_name}/{A}"
    snap_src2 = f"{pool_name}/{AA}"
    snap_name2 = f"{snap_src1}@{SNAP2}"
    snap_name3 = f"{snap_src2}@{SNAP3}"
    rv = call(
        "zfs.resource.destroy",
        {
            "paths": [snap_name2, snap_name3],
            "recursive": True,
        },
    )
    assert rv[snap_name2] is None
    assert rv[snap_name3] is None
    rv = call(
        "zfs.resource.query",
        {
            "paths": [snap_src1, snap_src2],
            "properties": None,
            "get_snapshots": True,
            "get_children": True,
        },
    )
    assert rv
    for i in rv:
        assert snap_name2 not in rv[0]["snapshots"]
        assert snap_name3 not in rv[0]["snapshots"]

    # Destroy all snapshots recursive
    snap_src1 = f"{pool_name}/{A}@*"
    snap_src2 = f"{pool_name}/{AA}@*"
    snap_src3 = f"{pool_name}/{AAA}@*"
    rv = call(
        "zfs.resource.destroy",
        {
            "paths": [snap_src1, snap_src2, snap_src3],
            "recursive": True,
        },
    )
    assert rv[snap_src1] is None
    assert rv[snap_src2] is None
    assert rv[snap_src3] is None
    rv = call(
        "zfs.resource.query",
        {
            "paths": [pool_name],
            "get_children": True,
            "get_snapshots": True,
        },
    )
    assert rv
    for i in rv:
        assert not i["snapshots"]
