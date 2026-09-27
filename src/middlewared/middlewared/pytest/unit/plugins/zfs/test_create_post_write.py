import errno
import logging
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from middlewared.api.current import ZFSResourceCreateArgsData
from middlewared.plugins.zfs import resource_create
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service import ServiceContext
from middlewared.service_exception import CallError


def request(path="tank/new", **kwargs):
    return ZFSResourceCreateArgsData(path=path, **kwargs)


def row(name, type_="FILESYSTEM", **props):
    return {
        "name": name,
        "type": type_,
        "properties": {key: {"raw": str(value), "value": value} for key, value in props.items()},
    }


class Stand:
    def __init__(self, rows, monkeypatch):
        self.rows = {r["name"]: r for r in rows}
        self.list_paths = []
        self.zpool_reads = []
        self.created = []
        middleware = Middleware()
        middleware["zpool.query_impl"] = self.zpool_query_impl
        middleware.services.zfs.tier.config = lambda: SimpleNamespace(enabled=False)
        middleware.services.zfs.resource.list_impl = self.list_impl
        middleware.call_hook_sync = Mock()
        self.middleware = middleware
        self.context = ServiceContext(middleware, logging.getLogger("test"))
        self.mount = Mock()
        self.destroy = Mock()
        monkeypatch.setattr(resource_create, "create_ancestors", self.create_ancestors)
        monkeypatch.setattr(resource_create, "create_leaf", self.create_leaf)
        monkeypatch.setattr(resource_create, "mount_impl", self.mount)
        monkeypatch.setattr(resource_create, "destroy_nonrecursive_impl", self.destroy)

    def zpool_query_impl(self, args):
        self.zpool_reads.append(args)
        return []

    def list_impl(self, query):
        self.list_paths.append(list(query.paths))
        return [self.rows[path] for path in query.paths if path in self.rows]

    def create_ancestors(self, tls, missing, mount):
        for path in missing:
            self.rows[path] = {"name": path, "type": "FILESYSTEM", "properties": {}}
        return list(missing)

    def create_leaf(self, tls, path, type_, props, user_properties, crypto):
        self.created.append((path, type_, props, user_properties, crypto))
        self.rows[path] = {"name": path, "type": type_, "properties": {}}

    def create(self, data):
        return resource_create.create_impl(self.context, Mock(), data)


@pytest.mark.parametrize(
    "path, kwargs, announced",
    [("tank/ix-apps/x", {"bypass": True}, [])],
)
def test_create_announces_created_ancestors_then_the_leaf(monkeypatch, path, kwargs, announced):
    fs = {"readonly": "off", "encryption": "off", "acltype": "nfsv4", "aclmode": "passthrough"}
    stand = Stand(
        [row("tank", mountpoint="/mnt/tank", **fs), row("tank/ix-apps", mountpoint="/mnt/.ix-apps", **fs)], monkeypatch
    )
    stand.create(request(path=path, **kwargs))
    assert [c.kwargs["id"] for c in stand.middleware.send_event.call_args_list] == announced
    assert all(c.args == ("zfs.resource.list", "ADDED") for c in stand.middleware.send_event.call_args_list)


@pytest.mark.parametrize(
    "mount_fails, record_fails, destroy_fails, expected_errno, destroyed",
    [
        (True, False, False, None, False),
        (False, True, True, errno.EBUSY, True),
    ],
)
def test_create_keeps_or_removes_the_leaf_on_post_write_failure(
    monkeypatch, mount_fails, record_fails, destroy_fails, expected_errno, destroyed
):
    fs = {"mountpoint": "/mnt/tank", "encryption": "off", "acltype": "nfsv4", "aclmode": "passthrough"}
    stand = Stand([row("tank", readonly="off", **fs)], monkeypatch)
    failure = RuntimeError("sentinel failure")
    if mount_fails:
        stand.mount.side_effect = failure
    if destroy_fails:
        stand.destroy.side_effect = failure
    record = Mock(side_effect=failure if record_fails else None)
    stand.middleware["pool.dataset.insert_or_update_encrypted_record"] = record
    with pytest.raises(CallError) as exc_info:
        stand.create(request(path="tank/enc", encryption={"generate_key": True}))
    assert "'tank/enc'" in exc_info.value.errmsg
    if expected_errno is not None:
        assert exc_info.value.errno == expected_errno
    record.assert_called_once()
    assert stand.destroy.called is destroyed
    if mount_fails:
        assert stand.middleware.send_event.call_args_list == [
            call("zfs.resource.list", "ADDED", id="tank/enc", fields=stand.rows["tank/enc"])
        ]
