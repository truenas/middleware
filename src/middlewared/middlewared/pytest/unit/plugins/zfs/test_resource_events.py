import functools
import logging
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from middlewared.api.current import (
    ZFSResourceCreateArgsData,
    ZFSResourcePromoteArgsData,
    ZFSResourceRenameArgsData,
    ZFSResourceSetArgsData,
)
from middlewared.plugins.zfs import (
    resource_create,
    resource_destroy,
    resource_ops,
    resource_query,
    resource_set,
    set_rules,
)
from middlewared.plugins.zfs.resource import ZFSResourceService
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service_exception import CallError


def prop(value):
    return {"value": value, "raw": str(value), "source": None}


def entry(name, properties=None, user_properties=None):
    return {
        "name": name,
        "pool": name.split("/")[0],
        "type": "FILESYSTEM",
        "createtxg": 10,
        "guid": 20,
        "properties": properties,
        "user_properties": user_properties,
        "children": None,
    }


@pytest.fixture
def service():
    return ZFSResourceService(Middleware())


@pytest.fixture
def written(monkeypatch):
    calls = []

    def set_impl(tls, path, properties, user_properties, inherit, bypass):
        calls.append((path, properties, user_properties, inherit))
        return written.result

    written = SimpleNamespace(calls=calls, result=None)
    monkeypatch.setattr(resource_set, "set_impl", set_impl)
    return written


@pytest.mark.parametrize(
    "kwargs, result_props, result_user, descendants_affected",
    [
        ({"properties": {"compression": "gzip"}}, {"compression": prop("gzip-6")}, None, True),
        ({"properties": {"quota": 1073741824}}, {"quota": prop(1073741824)}, None, False),
        ({"user_properties": {"org.truenas:x": "1"}}, None, {"org.truenas:x": "1", "org.truenas:y": "2"}, True),
    ],
)
def test_set_impl_emits_one_changed_event_with_what_was_written(
    service, written, kwargs, result_props, result_user, descendants_affected
):
    written.result = entry("tank/a", result_props, result_user)
    assert service.set_impl(Mock(), "tank/a", **kwargs) is written.result
    service.middleware.send_event.assert_called_once_with(
        "zfs.resource.list",
        "CHANGED",
        id="tank/a",
        fields={
            "properties": result_props,
            "user_properties": result_user,
            "inherited": [],
            "descendants_affected": descendants_affected,
        },
    )


@pytest.mark.parametrize("inherit", [["sync", "atime"], ["org.truenas:x"]])
def test_set_impl_changed_event_lists_inherited_names_sorted(service, written, inherit):
    written.result = entry("tank/a", {"atime": prop("on"), "sync": prop("standard")})
    service.set_impl(Mock(), "tank/a", properties={"quota": 0}, inherit=iter(inherit))
    assert written.calls == [("tank/a", {"quota": 0}, None, inherit)]
    service.middleware.send_event.assert_called_once_with(
        "zfs.resource.list",
        "CHANGED",
        id="tank/a",
        fields={
            "properties": written.result["properties"],
            "user_properties": None,
            "inherited": sorted(inherit),
            "descendants_affected": True,
        },
    )


def test_set_impl_that_fails_to_write_emits_nothing(service, monkeypatch):
    def set_impl(*args):
        raise CallError("write failed")

    monkeypatch.setattr(resource_set, "set_impl", set_impl)
    with pytest.raises(CallError):
        service.set_impl(Mock(), "tank/a", properties={"compression": "gzip"})
    service.middleware.send_event.assert_not_called()


def test_create_impl_emits_one_added_event_with_the_returned_entry(service, monkeypatch):
    created = entry("tank/new", {"compression": prop("lz4")})
    monkeypatch.setattr(resource_create, "create_impl", lambda context, tls, data: created)
    assert service.create_impl(Mock(), ZFSResourceCreateArgsData(path="tank/new")) is created
    service.middleware.send_event.assert_called_once_with("zfs.resource.list", "ADDED", id="tank/new", fields=created)


def test_create_impl_that_fails_emits_nothing(service, monkeypatch):
    def create_impl(context, tls, data):
        raise CallError("create failed")

    monkeypatch.setattr(resource_create, "create_impl", create_impl)
    with pytest.raises(CallError):
        service.create_impl(Mock(), ZFSResourceCreateArgsData(path="tank/new"))
    service.middleware.send_event.assert_not_called()


@pytest.fixture
def listed(monkeypatch):
    queries = []

    def list_impl(context, tls, data):
        queries.append(data)
        return listed.rows

    listed = SimpleNamespace(queries=queries, rows=[])
    monkeypatch.setattr(resource_query, "list_impl", list_impl)
    return listed


def test_rename_impl_emits_removed_for_the_old_name_then_added_for_the_new(service, monkeypatch, listed):
    monkeypatch.setattr(resource_ops, "rename_impl", lambda tls, data: None)
    listed.rows = [entry("tank/new")]
    service.rename_impl(Mock(), ZFSResourceRenameArgsData(current_name="tank/old", new_name="tank/new"))
    assert service.middleware.send_event.call_args_list == [
        call("zfs.resource.list", "REMOVED", id="tank/old"),
        call("zfs.resource.list", "ADDED", id="tank/new", fields=listed.rows[0]),
    ]
    assert [(q.paths, q.properties) for q in listed.queries] == [(["tank/new"], None)]


def test_rename_impl_that_fails_emits_nothing(service, monkeypatch, listed):
    def rename_impl(tls, data):
        raise CallError("rename failed")

    monkeypatch.setattr(resource_ops, "rename_impl", rename_impl)
    with pytest.raises(CallError):
        service.rename_impl(Mock(), ZFSResourceRenameArgsData(current_name="tank/old", new_name="tank/new"))
    service.middleware.send_event.assert_not_called()


def test_promote_impl_emits_one_changed_event_holding_only_origin(service, monkeypatch, listed):
    monkeypatch.setattr(resource_ops, "promote_impl", lambda tls, data: None)
    listed.rows = [entry("tank/clone", {"origin": prop("")})]
    service.promote_impl(Mock(), ZFSResourcePromoteArgsData(path="tank/clone"))
    service.middleware.send_event.assert_called_once_with(
        "zfs.resource.list",
        "CHANGED",
        id="tank/clone",
        fields={
            "properties": {"origin": prop("")},
            "user_properties": None,
            "inherited": [],
            "descendants_affected": False,
        },
    )
    assert [(q.paths, q.properties) for q in listed.queries] == [(["tank/clone"], ["origin"])]


def test_destroy_impl_emits_nothing(service, monkeypatch):
    destroyed = []
    monkeypatch.setattr(resource_destroy, "destroy_impl", lambda context, tls, path, *args: destroyed.append(path))
    service.destroy_impl(Mock(), "tank/a")
    assert destroyed == ["tank/a"]
    service.middleware.send_event.assert_not_called()


class ServiceContextStub:
    def __init__(self, service, target):
        self.middleware = service.middleware
        self.logger = logging.getLogger("test_resource_events")
        self.s = SimpleNamespace(
            zfs=SimpleNamespace(
                resource=SimpleNamespace(
                    list_impl=lambda query: [target],
                    set_impl=functools.partial(service.set_impl, Mock()),
                ),
            ),
        )

    def call_sync2(self, method, *args, **kwargs):
        return method(*args, **kwargs)


@pytest.fixture
def through_set(monkeypatch, service, written):
    names = set_rules.MODEL_NATIVES
    monkeypatch.setattr(set_rules, "ZFSProperty", {name.upper(): name for name in names})
    monkeypatch.setattr(set_rules, "PROPERTY_TEMPLATES", SimpleNamespace(fs=names, vol=names))
    target = entry(
        "tank/a", {"compression": {"value": "lz4", "raw": "lz4", "source": {"type": "LOCAL", "value": None}}}
    )
    written.result = entry("tank/a", {"compression": prop("gzip")})
    service.context = ServiceContextStub(service, target)
    return service


def test_set_emits_changed_through_set_impl(through_set, written):
    through_set.set(ZFSResourceSetArgsData(path="tank/a", properties={"compression": "gzip"}))
    through_set.middleware.send_event.assert_called_once_with(
        "zfs.resource.list",
        "CHANGED",
        id="tank/a",
        fields={
            "properties": written.result["properties"],
            "user_properties": None,
            "inherited": [],
            "descendants_affected": True,
        },
    )


def test_set_dry_run_emits_nothing(through_set, written):
    through_set.set(ZFSResourceSetArgsData(path="tank/a", properties={"compression": "gzip"}, dry_run=True))
    assert written.calls == []
    through_set.middleware.send_event.assert_not_called()
