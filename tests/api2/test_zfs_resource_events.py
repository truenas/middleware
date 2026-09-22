import contextlib
import os
import pprint
import time

import pytest

from auto_config import pool_name
from middlewared.test.integration.utils import call, client, ssh

GiB = 1024**3
MiB = 1024**2
SETTLE = 5


@contextlib.contextmanager
def resource(name, **data):
    path = os.path.join(pool_name, name)
    call("zfs.resource.create", {"path": path, **data})
    try:
        yield path
    finally:
        call("zfs.resource.destroy", {"path": path, "recursive": True})


@contextlib.contextmanager
def collect(prefix, collections=("zfs.resource.list",)):
    events = []

    def callback(mtype, **message):
        id_ = message.get("id") or ""
        if id_ == prefix or id_.startswith((f"{prefix}/", f"{prefix}@")):
            events.append((message["collection"], mtype, id_, message))

    with client() as c:
        for collection in collections:
            c.subscribe(collection, callback, sync=True)
        yield events
        time.sleep(SETTLE)


def summary(events):
    return [(collection, mtype, id_) for collection, mtype, id_, _ in events]


@pytest.mark.parametrize(
    "data, properties, descendants_affected",
    [
        (
            {"type": "VOLUME", "properties": {"volsize": 64 * MiB, "refreservation": "none"}},
            {"compression": "zstd"},
            True,
        ),
        ({}, {"quota": GiB}, False),
    ],
)
def test_set_emits_one_changed_event(data, properties, descendants_affected):
    with resource("zre_events_set", **data) as path:
        with collect(path) as events:
            call("zfs.resource.set", {"path": path, "properties": properties})

        assert summary(events) == [("zfs.resource.list", "CHANGED", path)], pprint.pformat(events)
        fields = events[0][3]["fields"]
        assert set(fields["properties"]) == set(properties)
        assert fields["user_properties"] is None
        assert fields["inherited"] == []
        assert fields["descendants_affected"] is descendants_affected


def test_update_impl_emits_changed_event():
    with resource("zre_events_update_impl") as path:
        with collect(path) as events:
            call("pool.dataset.update_impl", {"name": path, "zprops": {"compression": "lz4"}})

        assert summary(events) == [("zfs.resource.list", "CHANGED", path)], pprint.pformat(events)
        assert set(events[0][3]["fields"]["properties"]) == {"compression"}


def test_rename_emits_removed_then_added():
    with resource("zre_events_rename") as parent:
        call("zfs.resource.create", {"path": f"{parent}/a"})
        with collect(parent) as events:
            call("zfs.resource.rename", {"current_name": f"{parent}/a", "new_name": f"{parent}/b"})

        assert summary(events) == [
            ("zfs.resource.list", "REMOVED", f"{parent}/a"),
            ("zfs.resource.list", "ADDED", f"{parent}/b"),
        ], pprint.pformat(events)


def test_shell_destroy_reaches_both_streams():
    with resource("zre_events_shell_destroy") as parent:
        child = f"{parent}/child"
        ssh(f"zfs create {child}")
        with collect(child, ("zfs.resource.list", "pool.dataset.query")) as events:
            ssh(f"zfs destroy {child}")

        assert sorted(summary(events)) == [
            ("pool.dataset.query", "REMOVED", child),
            ("zfs.resource.list", "REMOVED", child),
        ], pprint.pformat(events)


def test_resource_destroy_emits_one_removed():
    with resource("zre_events_api_destroy") as parent:
        child = f"{parent}/child"
        call("zfs.resource.create", {"path": child})
        with collect(child) as events:
            call("zfs.resource.destroy", {"path": child})

        assert summary(events) == [("zfs.resource.list", "REMOVED", child)], pprint.pformat(events)


def test_snapshot_destroy_emits_nothing():
    with resource("zre_events_snapshot_destroy") as path:
        ssh(f"zfs snapshot {path}@snap")
        with collect(path) as events:
            ssh(f"zfs destroy {path}@snap")

        assert summary(events) == [], pprint.pformat(events)


def test_internal_dataset_destroy_emits_removed():
    with resource("zre_events_internal") as parent:
        internal = f"{parent}/ix-apps/child"
        ssh(f"zfs create -p {internal}")
        with collect(internal) as events:
            ssh(f"zfs destroy {internal}")

        assert summary(events) == [("zfs.resource.list", "REMOVED", internal)], pprint.pformat(events)


def test_replication_receive_emits_no_removed():
    with resource("zre_events_receive") as parent:
        source = f"{parent}/source"
        target = f"{parent}/target"
        ssh(f"zfs create {source}")
        ssh(f"zfs snapshot {source}@s1")
        ssh(f"zfs snapshot {source}@s2")
        with collect(target) as events:
            ssh(f"zfs send {source}@s1 | zfs recv -u {target}")
            ssh(f"zfs send -i @s1 {source}@s2 | zfs recv -u -F {target}")

        assert [e for e in summary(events) if e[1] == "REMOVED"] == [], pprint.pformat(events)
