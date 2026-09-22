import asyncio
import errno
import inspect
import logging
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from middlewared.api.current import ZFSResourceSetArgsData
from middlewared.plugins.zfs import resource_set, set_rules, zvol_utils
from middlewared.plugins.zfs.delegates import (
    ZFSResourceDelegate,
    participating,
    run_after,
    run_validate,
    validate_delegate,
)
from middlewared.plugins.zfs.resource import ZFSResourceService
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service_exception import CallError, ValidationError, ValidationErrors

BOTH = ("FILESYSTEM", "VOLUME")
FS_VALUES = {
    "acltype": "nfsv4",
    "aclmode": "passthrough",
    "aclinherit": "passthrough",
    "compression": "lz4",
    "snapdev": "hidden",
}


@pytest.fixture(autouse=True)
def type_masks(monkeypatch):
    names = set_rules.MODEL_NATIVES
    monkeypatch.setattr(set_rules, "ZFSProperty", {name.upper(): name for name in names})
    monkeypatch.setattr(set_rules, "PROPERTY_TEMPLATES", SimpleNamespace(fs=names, vol=names))


def fake(name, triggers=("compression",), types=BOTH, validate=None, after=None, log=None):
    log = [] if log is None else log

    async def validate_set(self, state, verrors):
        log.append((name, "validate", state))
        if validate is not None:
            validate(state, verrors)

    async def after_set(self, state, entry):
        log.append((name, "after", entry))
        if after is not None:
            after(state, entry)

    cls = type(
        "FakeDelegate",
        (ZFSResourceDelegate,),
        {
            "name": name,
            "types": frozenset(types),
            "triggers": frozenset(triggers),
            "validate_set": validate_set,
            "after_set": after_set,
        },
    )
    return cls(Mock())


def row(name, type_="FILESYSTEM", **values):
    return {
        "name": name,
        "pool": name.split("/")[0],
        "type": type_,
        "createtxg": 10,
        "guid": 20,
        "properties": {
            n: {"value": v, "raw": str(v), "source": {"type": "LOCAL", "value": None}} for n, v in values.items()
        },
        "user_properties": None,
        "children": [],
    }


class Context:
    def __init__(self, target, log=None):
        self.target = target
        self.log = [] if log is None else log
        self.bridged = 0
        self.logger = logging.getLogger("test_delegates")
        self.middleware = SimpleNamespace(run_coroutine=self.run_coroutine)
        self.s = SimpleNamespace(
            zfs=SimpleNamespace(resource=SimpleNamespace(list_impl="list_impl", set_impl="set_impl")),
        )

    def run_coroutine(self, coro):
        self.bridged += 1
        return asyncio.run(coro)

    def call_sync2(self, method, *args, **kwargs):
        if method == "list_impl":
            return [self.target]
        if method == "set_impl":
            self.log.append(("set_impl", args[0]))
            return {**self.target, "properties": None, "user_properties": None, "children": None}
        raise AssertionError(method)

    def written(self):
        return [entry for entry in self.log if entry[0] == "set_impl"]


def filesystem(log=None):
    return Context(row("tank/a", **FS_VALUES), log)


def set_(context, delegates, path="tank/a", **kwargs):
    return resource_set.set(context, ZFSResourceSetArgsData(path=path, **kwargs), delegates)


def steps(log):
    return [entry[:2] for entry in log]


def add_error(attribute, message):
    def validate(state, verrors):
        verrors.add(attribute, message, errno.EINVAL)

    return validate


def raising(exc):
    def hook(*args):
        raise exc

    return hook


def test_participating_selects_intersecting_triggers_ordered_by_name():
    b = fake("b", triggers=("compression",))
    a = fake("a", triggers=("quota", "compression"))
    c = fake("c", triggers=("acltype",))
    assert participating([b, c, a], frozenset({"compression"})) == [a, b]


def test_set_runs_no_delegate_whose_triggers_are_untouched():
    log = []
    context = filesystem(log)
    set_(context, [fake("acl", triggers=("acltype",), log=log)], properties={"compression": "gzip"})
    assert steps(log) == [("set_impl", "tank/a")]
    assert context.bridged == 0


def test_set_runs_no_delegate_for_another_resource_type():
    log = []
    delegates = [fake("vol", types=("VOLUME",), log=log), fake("fs", types=("FILESYSTEM",), log=log)]
    set_(filesystem(log), delegates, properties={"compression": "gzip"})
    assert steps(log) == [("fs", "validate"), ("set_impl", "tank/a"), ("fs", "after")]


def test_set_validates_before_the_write_and_runs_after_set_with_the_written_entry():
    log = []
    delegates = [fake("b", log=log), fake("a", log=log)]
    entry = set_(filesystem(log), delegates, properties={"compression": "gzip"})
    assert steps(log) == [
        ("a", "validate"),
        ("b", "validate"),
        ("set_impl", "tank/a"),
        ("a", "after"),
        ("b", "after"),
    ]
    assert log[3][2] is entry
    assert log[0][2].effective("compression") == "gzip"


def test_set_aggregates_delegate_and_rule_errors_into_one_validation_errors():
    log = []
    context = filesystem(log)
    delegates = [
        fake("two", triggers=("acltype",), validate=add_error("zfs.resource.set.properties.acltype", "second")),
        fake("one", triggers=("acltype",), validate=add_error("zfs.resource.set.properties.acltype", "first")),
    ]
    with pytest.raises(ValidationErrors) as ei:
        set_(context, delegates, properties={"acltype": "posix", "aclmode": "passthrough"})
    assert [(e.attribute, e.errmsg) for e in ei.value.errors] == [
        (
            "zfs.resource.set.properties.aclmode",
            "'aclmode' must be discard when the effective 'acltype' is posix or off.",
        ),
        ("zfs.resource.set.properties.acltype", "first"),
        ("zfs.resource.set.properties.acltype", "second"),
    ]
    assert context.written() == []


@pytest.mark.parametrize(
    "exc",
    [
        ValidationError("zfs.resource.set.properties.compression", "raised alone", errno.EINVAL),
        ValidationErrors([ValidationError("zfs.resource.set.properties.compression", "raised alone", errno.EINVAL)]),
    ],
)
def test_set_adds_a_raised_validation_error_and_fails_closed(exc):
    log = []
    context = filesystem(log)
    with pytest.raises(ValidationErrors) as ei:
        set_(context, [fake("raiser", validate=raising(exc), log=log)], properties={"compression": "gzip"})
    assert [(e.attribute, e.errmsg) for e in ei.value.errors] == [
        ("zfs.resource.set.properties.compression", "raised alone")
    ]
    assert steps(log) == [("raiser", "validate")]


def test_set_refuses_a_request_a_broken_delegate_could_not_judge():
    log = []
    context = filesystem(log)
    with pytest.raises(CallError) as ei:
        set_(
            context,
            [fake("fake.broken", validate=raising(KeyError("boom")), log=log)],
            properties={"compression": "gzip"},
        )
    assert ei.value.errmsg == "fake.broken: validation failed: 'boom'"
    assert context.written() == []


def test_set_reports_validation_errors_alongside_a_broken_delegate(caplog):
    context = filesystem()
    delegates = [
        fake("fake.broken", validate=raising(KeyError("boom"))),
        fake("fake.strict", validate=add_error("zfs.resource.set.properties.compression", "refused")),
    ]
    with pytest.raises(ValidationErrors) as ei:
        set_(context, delegates, properties={"compression": "gzip"})
    assert [e.errmsg for e in ei.value.errors] == ["refused"]
    assert [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR] == [
        "tank/a: delegate 'fake.broken' validate_set failed"
    ]
    assert context.written() == []


def test_set_returns_the_written_entry_when_an_after_set_fails(caplog):
    log = []
    context = filesystem(log)
    delegates = [fake("a", after=raising(RuntimeError("after failed")), log=log), fake("b", log=log)]
    entry = set_(context, delegates, properties={"compression": "gzip"})
    assert entry.name == "tank/a"
    assert steps(log)[-2:] == [("a", "after"), ("b", "after")]
    assert [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR] == [
        "tank/a: delegate 'a' after_set failed"
    ]


def test_set_dry_run_validates_delegates_and_runs_no_after_set():
    log = []
    set_(filesystem(log), [fake("a", log=log)], properties={"compression": "gzip"}, dry_run=True)
    assert steps(log) == [("a", "validate")]


@pytest.mark.parametrize(
    "type_, kwargs, expected",
    [
        ("VOLUME", {"properties": {"snapdev": "visible"}}, {"tank/vol@a", "tank/vol@b"}),
        ("VOLUME", {"inherit": ["snapdev"]}, {"tank/vol@a", "tank/vol@b"}),
        ("VOLUME", {"properties": {"compression": "gzip"}}, set()),
        ("FILESYSTEM", {"properties": {"snapdev": "visible"}}, set()),
    ],
)
def test_set_lists_snapshot_devices_only_for_a_volume_touching_snapdev(monkeypatch, type_, kwargs, expected):
    devices = ["tank/vol", "tank/vol@a", "tank/vol@b", "tank/vol2@c", "tank/other@a"]
    monkeypatch.setattr(zvol_utils, "unlocked_zvols_fast_impl", lambda: {name: {} for name in devices})
    log = []
    target = row("tank/vol", type_, snapdev="hidden", compression="lz4")
    parent = row("tank", snapdev="hidden")
    context = Context(target, log)
    context.call_sync2 = lambda method, *args, **kw: [target, parent] if method == "list_impl" else target
    delegate = fake("snap", triggers=("snapdev", "compression"), log=log)
    set_(context, [delegate], path="tank/vol", dry_run=True, **kwargs)
    [(_, _, state)] = log
    assert state.snapshot_devices == expected


def test_validate_delegate_accepts_a_well_formed_delegate():
    validate_delegate(fake("fine", triggers=("snapdev", "volsize"), types=BOTH))


@pytest.mark.parametrize(
    "name, types, triggers",
    [
        ("", BOTH, ("compression",)),
        ("bad.type", ("FILESYSTEM", "SNAPSHOT"), ("compression",)),
        ("bad.trigger", BOTH, ("compression", "volblocksize")),
    ],
)
def test_validate_delegate_rejects_a_malformed_delegate(name, types, triggers):
    with pytest.raises(ValueError):
        validate_delegate(fake(name, triggers=triggers, types=types))


@pytest.fixture
def service():
    return ZFSResourceService(Middleware())


def test_register_delegate_lists_registered_names_sorted(service):
    service.register_delegate(fake("b"))
    service.register_delegate(fake("a"))
    assert service.delegates() == ["a", "b"]


def test_register_delegate_refuses_a_second_delegate_with_the_same_name(service):
    first = fake("a")
    service.register_delegate(first)
    with pytest.raises(ValueError):
        service.register_delegate(fake("a"))
    assert service.delegates() == ["a"]
    assert service._delegates["a"] is first


def test_register_delegate_refuses_a_malformed_delegate(service):
    with pytest.raises(ValueError):
        service.register_delegate(fake("bad.trigger", triggers=("volblocksize",)))
    assert service.delegates() == []


def test_service_set_runs_the_registered_delegates(service):
    log = []
    service.register_delegate(fake("a", log=log))
    service.context = filesystem(log)
    service.set(ZFSResourceSetArgsData(path="tank/a", properties={"compression": "gzip"}))
    assert steps(log) == [("a", "validate"), ("set_impl", "tank/a"), ("a", "after")]


@pytest.mark.parametrize(
    "function",
    [ZFSResourceDelegate.validate_set, ZFSResourceDelegate.after_set, run_validate, run_after],
)
def test_delegate_hooks_are_coroutines(function):
    assert inspect.iscoroutinefunction(function)
