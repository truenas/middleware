import errno
from unittest.mock import Mock

import pytest

from middlewared.api.current import ZFSResourceSetProperties
from middlewared.plugins.iscsi_.extents import iSCSITargetExtentService
from middlewared.plugins.iscsi_.global_linux import ISCSIGlobalService
from middlewared.plugins.iscsi_.zfs_delegate import ISCSIExtentDelegate
from middlewared.plugins.zfs.delegates import validate_delegate
from middlewared.plugins.zfs.set_rules import PropertyView, SetContext
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service_exception import ValidationErrors

GiB = 1024**3
HIDDEN_MESSAGE = (
    "'tank/vol' has snapshots which have attachments being used. Before marking it as HIDDEN, remove attachment usages."
)


def volume(properties=None, inherit=(), parent=None, snapshot_devices=(), path="tank/vol", **current):
    return SetContext(
        path=path,
        type="VOLUME",
        properties=ZFSResourceSetProperties(**(properties or {})),
        user_properties={},
        inherit=frozenset(inherit),
        current=PropertyView(path, {"volsize": GiB, "readonly": "off", "snapdev": "visible", **current}),
        source=PropertyView(path, {}),
        parent=None if parent is None else PropertyView("tank", parent),
        pool_root=False,
        tier_enabled=None,
        dedup_entitlement=None,
        snapshot_devices=frozenset(snapshot_devices),
    )


def extents_on(*paths):
    m = Middleware()
    m["iscsi.extent.query"] = m._query_filter([{"id": i, "path": f"zvol/{p}"} for i, p in enumerate(paths, 1)])
    return m


async def validate(m, state):
    verrors = ValidationErrors()
    await ISCSIExtentDelegate(m).validate_set(state, verrors)
    return list(verrors)


def test_extent_delegate_declaration():
    delegate = ISCSIExtentDelegate(Middleware())

    validate_delegate(delegate)
    assert (delegate.name, delegate.types, delegate.triggers) == (
        "iscsi.extent",
        frozenset({"VOLUME"}),
        frozenset({"volsize", "readonly", "snapdev"}),
    )


@pytest.mark.parametrize(
    "kwargs, attribute",
    [
        ({"properties": {"snapdev": "hidden"}}, "zfs.resource.set.properties.snapdev"),
        ({"inherit": ["snapdev"], "parent": {"snapdev": "hidden"}}, "zfs.resource.set.inherit.snapdev"),
    ],
)
@pytest.mark.asyncio
async def test_hiding_snapshot_devices_backing_an_extent_is_rejected(kwargs, attribute):
    state = volume(snapshot_devices={"tank/vol@a", "tank/vol@b"}, **kwargs)

    assert await validate(extents_on("tank/vol@b"), state) == [(attribute, HIDDEN_MESSAGE, errno.EINVAL)]


@pytest.mark.parametrize(
    "path, device, stored",
    [
        ("tank/tpv sp", "tank/tpv sp@s1", "zvol/tank/tpv+sp@s1"),
        ("tank/vol", "tank/vol@s 1", "zvol/tank/vol@s+1"),
        ("tank/a b c", "tank/a b c@x y", "zvol/tank/a+b+c@x+y"),
    ],
    ids=["space-in-volume", "space-in-snapshot", "several-spaces"],
)
@pytest.mark.asyncio
async def test_hiding_a_snapshot_device_with_an_encoded_extent_path_is_rejected(path, device, stored):
    m = Middleware()
    m["iscsi.extent.query"] = m._query_filter([{"id": 1, "path": stored}])
    state = volume(path=path, snapshot_devices={device}, properties={"snapdev": "hidden"})

    assert await validate(m, state) == [
        (
            "zfs.resource.set.properties.snapdev",
            f"{path!r} has snapshots which have attachments being used. Before marking it as HIDDEN, remove "
            "attachment usages.",
            errno.EINVAL,
        )
    ]


@pytest.mark.asyncio
async def test_snapshot_devices_are_looked_up_by_their_encoded_extent_path():
    filters = []
    m = Middleware()
    m["iscsi.extent.query"] = lambda *args: filters.append(args[0]) or []
    state = volume(
        path="tank/tpv sp", snapshot_devices={"tank/tpv sp@s2", "tank/tpv sp@s1"}, properties={"snapdev": "hidden"}
    )

    assert await validate(m, state) == []
    assert filters == [[["path", "in", ["zvol/tank/tpv+sp@s1", "zvol/tank/tpv+sp@s2"]]]]


@pytest.mark.parametrize(
    "extent, kwargs",
    [
        ("tank/other@a", {"properties": {"snapdev": "hidden"}}),
        ("tank/vol@a", {"properties": {"snapdev": "visible"}, "snapdev": "hidden"}),
        ("tank/vol@a", {"properties": {"snapdev": "hidden"}, "snapdev": "hidden"}),
        ("tank/vol@a", {"inherit": ["snapdev"], "parent": {"snapdev": "visible"}, "snapdev": "hidden"}),
    ],
    ids=["extent-elsewhere", "showing", "already-hidden", "inherit-visible"],
)
@pytest.mark.asyncio
async def test_snapdev_change_without_an_attached_hidden_device_is_accepted(extent, kwargs):
    state = volume(snapshot_devices={"tank/vol@a"}, **kwargs)

    assert await validate(extents_on(extent), state) == []


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        ({"properties": {"volsize": 2 * GiB}}, [("resync_lun_size_for_zvol", ("tank/vol",))]),
        ({"properties": {"volsize": GiB}}, []),
        (
            {"properties": {"readonly": "ON"}, "readonly": "on"},
            [("resync_readonly_property_for_zvol", ("tank/vol", "on"))],
        ),
        (
            {"inherit": ["readonly"], "parent": {"readonly": "on"}},
            [("resync_readonly_property_for_zvol", ("tank/vol", "on"))],
        ),
        (
            {"properties": {"volsize": 2 * GiB, "readonly": "off"}},
            [
                ("resync_lun_size_for_zvol", ("tank/vol",)),
                ("resync_readonly_property_for_zvol", ("tank/vol", "off")),
            ],
        ),
    ],
    ids=["grow", "same-size", "readonly-unchanged", "readonly-inherited", "both"],
)
@pytest.mark.asyncio
async def test_after_set_resyncs_the_extent(kwargs, expected):
    calls = []
    m = Middleware()
    for method in ("resync_lun_size_for_zvol", "resync_readonly_property_for_zvol"):
        m[f"iscsi.global.{method}"] = lambda *args, method=method: calls.append((method, args))

    await ISCSIExtentDelegate(m).after_set(volume(**kwargs), None)

    assert calls == expected


def extent_service():
    calls = []
    m = Middleware()
    for name in ("iscsi.extent.validate", "iscsi.extent.save", "pool.dataset.update_impl", "datastore.update"):
        m[name] = lambda *args, name=name: calls.append((name, args))
    m.register_hook = Mock()
    svc = iSCSITargetExtentService(m)
    extent = {"id": 7, "name": "lun", "path": "zvol/tank/vol", "ro": False, "enabled": True, "locked": False}

    async def get_instance(id_):
        return dict(extent)

    async def nothing(*args, **kwargs):
        pass

    svc.get_instance = get_instance
    svc.clean = nothing
    svc._service_change = nothing
    return svc, calls


def called(calls, name):
    return [args for method, args in calls if method == name]


@pytest.mark.asyncio
async def test_update_internal_without_zfs_sync_only_updates_the_extent():
    svc, calls = extent_service()

    await svc.update_internal(7, {"ro": True}, sync_zfs=False)

    assert called(calls, "pool.dataset.update_impl") == []
    assert called(calls, "datastore.update")[0][2]["ro"] is True


@pytest.mark.asyncio
async def test_update_internal_with_zfs_sync_writes_readonly_to_the_zvol():
    svc, calls = extent_service()

    await svc.update_internal(7, {"ro": True}, sync_zfs=True)

    assert called(calls, "pool.dataset.update_impl") == [({"name": "tank/vol", "zprops": {"readonly": "on"}},)]


def test_readonly_resync_updates_the_extent_without_writing_back_to_zfs():
    calls = []
    m = Middleware()
    m["iscsi.extent.query"] = lambda *args: {"id": 7, "ro": False}
    m["iscsi.extent.update"] = lambda *args: calls.append(("update", args))
    m["iscsi.extent.update_internal"] = lambda *args: calls.append(("update_internal", args))

    ISCSIGlobalService(m).resync_readonly_property_for_zvol("tank/vol", "on")

    assert calls == [("update_internal", (7, {"ro": True}, False))]


@pytest.mark.asyncio
async def test_do_update_audits_and_writes_readonly_to_the_zvol():
    svc, calls = extent_service()
    audit_callback = Mock()

    await svc.do_update(audit_callback, 7, {"ro": True})

    audit_callback.assert_called_once_with("lun")
    assert called(calls, "pool.dataset.update_impl") == [({"name": "tank/vol", "zprops": {"readonly": "on"}},)]
