import logging
from types import SimpleNamespace

import pytest

from middlewared.api.current import ZFSResourceSetArgsData, ZFSResourceSetProperties
from middlewared.plugins.zfs import set_rules
from middlewared.plugins.zfs.set_rules import (
    INDEX_PROPERTIES,
    INHERITABLE_PROPERTIES,
    MODEL_NATIVES,
    NON_INHERITABLE_PROPERTIES,
    POOL_ROOT_INHERIT_VALUES,
    SET_READ_PROPERTIES,
    SET_RULES,
    SETTABLE_PROPERTIES,
    PropertyView,
    SetContext,
    SetRule,
    apply_acl_coupling,
    apply_thick_follow,
    check_acl_combination,
    check_has_work,
    check_inherit_names,
    check_set_inherit_conflict,
    check_user_properties,
    validate_request,
    validate_set,
)
from middlewared.service_exception import CallError, ValidationError, ValidationErrors

MiB = 1024**2
GiB = 1024**3
PATH = "tank/a"

SETTABLE = frozenset(
    {
        "aclinherit",
        "aclmode",
        "acltype",
        "atime",
        "checksum",
        "compression",
        "copies",
        "dedup",
        "exec",
        "quota",
        "readonly",
        "recordsize",
        "refquota",
        "refreservation",
        "reservation",
        "snapdev",
        "snapdir",
        "special_small_blocks",
        "sync",
        "volsize",
        "xattr",
    }
)
PRIVATE_NATIVES = frozenset(
    {"canmount", "mountpoint", "overlay", "prefetch", "primarycache", "secondarycache", "setuid"}
)
READ = SETTABLE | {"available", "volblocksize", "usedbyrefreservation"}
FILESYSTEM_NAMES = READ - {"volsize", "volblocksize"}
VOLUME_NAMES = frozenset(
    {
        "available",
        "checksum",
        "compression",
        "copies",
        "dedup",
        "readonly",
        "refreservation",
        "reservation",
        "snapdev",
        "special_small_blocks",
        "sync",
        "usedbyrefreservation",
        "volblocksize",
        "volsize",
    }
)
BENIGN = {
    "aclinherit": "passthrough",
    "aclmode": "passthrough",
    "acltype": "nfsv4",
    "atime": "on",
    "available": 100 * GiB,
    "checksum": "on",
    "compression": "lz4",
    "copies": 1,
    "dedup": "off",
    "exec": "on",
    "quota": 0,
    "readonly": "off",
    "recordsize": 131072,
    "refquota": 0,
    "refreservation": 0,
    "reservation": 0,
    "snapdev": "hidden",
    "snapdir": "hidden",
    "special_small_blocks": 0,
    "sync": "standard",
    "usedbyrefreservation": 0,
    "volblocksize": 16384,
    "volsize": GiB,
    "xattr": "sa",
}
FILESYSTEM_NATIVES = (SETTABLE | PRIVATE_NATIVES) - {"volsize"}
VOLUME_NATIVES = frozenset(
    {
        "checksum",
        "compression",
        "copies",
        "dedup",
        "prefetch",
        "primarycache",
        "readonly",
        "refreservation",
        "reservation",
        "secondarycache",
        "snapdev",
        "special_small_blocks",
        "sync",
        "volsize",
    }
)
EVERY_NATIVE = {
    **{name: value for name, value in BENIGN.items() if name in SETTABLE},
    "canmount": "on",
    "mountpoint": "/mnt/tank/a",
    "overlay": "on",
    "prefetch": "all",
    "primarycache": "all",
    "secondarycache": "all",
    "setuid": "on",
}
DENIED = SimpleNamespace(entitled=False, message="SENTINEL entitlement denial")
ALLOWED = SimpleNamespace(entitled=True, message="")


@pytest.fixture(autouse=True)
def type_masks(monkeypatch):
    monkeypatch.setattr(set_rules, "ZFSProperty", {name.upper(): name for name in SETTABLE | PRIVATE_NATIVES})
    monkeypatch.setattr(set_rules, "PROPERTY_TEMPLATES", SimpleNamespace(fs=FILESYSTEM_NATIVES, vol=VOLUME_NATIVES))


@pytest.fixture(autouse=True)
def max_recordsize(monkeypatch, tmp_path):
    path = tmp_path / "zfs_max_recordsize"
    path.write_text(f"{16 * MiB}\n")
    monkeypatch.setattr(set_rules, "ZFS_MAX_RECORDSIZE", str(path))
    return path


def descendant(name, ssb, dedup_source, inherited_from=None, type_="FILESYSTEM"):
    return {
        "name": name,
        "type": type_,
        "properties": {
            "dedup": {"value": "off", "source": {"type": dedup_source, "value": inherited_from}},
            "special_small_blocks": {"value": ssb, "source": {"type": "LOCAL", "value": None}},
        },
    }


PERFORMANCE_CHILD = descendant(f"{PATH}/b", 131072, "INHERITED", "tank")


class RecordingContext:
    def __init__(self, special_vdev=True, draid=False, descendants=()):
        self.special_vdev = special_vdev
        self.draid = draid
        self.descendants = list(descendants)
        self.calls = []
        self.middleware = SimpleNamespace(call_sync=self.call_sync)
        self.s = SimpleNamespace(zfs=SimpleNamespace(resource=SimpleNamespace(list_impl="zfs.resource.list_impl")))

    def call_sync(self, method, *args):
        if method == "zpool.query_impl" and args[0].get("topology"):
            self.calls.append("topology")
            vdev_type = "draid1:1d:3c:0s" if self.draid else "mirror"
            return [{"topology": {"data": [{"vdev_type": vdev_type}], "special": []}}]
        if method == "zpool.query_impl":
            self.calls.append("class_special_size")
            return [{"properties": {"class_special_size": {"value": GiB if self.special_vdev else 0}}}]
        raise AssertionError(f"unexpected call {method}")

    def call_sync2(self, method, query):
        self.calls.append(method)
        if method == "zfs.resource.list_impl" and query.get_children:
            return [descendant(query.paths[0], 0, "LOCAL"), *self.descendants]
        raise AssertionError(f"unexpected call {method}")


def view(type_, values=None, path=PATH):
    names = FILESYSTEM_NAMES if type_ == "FILESYSTEM" else VOLUME_NAMES
    return PropertyView(path, {n: v for n, v in {**BENIGN, **(values or {})}.items() if n in names})


def state(
    type_="FILESYSTEM",
    properties=None,
    inherit=(),
    current=None,
    source="LOCAL",
    parent=None,
    pool_root=False,
    tier_enabled=False,
    entitlement=ALLOWED,
    path=PATH,
):
    names = FILESYSTEM_NAMES if type_ == "FILESYSTEM" else VOLUME_NAMES
    return SetContext(
        path=path,
        type=type_,
        properties=ZFSResourceSetProperties(**(properties or {})),
        user_properties={},
        inherit=frozenset(inherit),
        current=view(type_, current, path),
        source=PropertyView(path, dict.fromkeys(names, source)),
        parent=None if parent is None else view("FILESYSTEM", parent, path.rsplit("/", 1)[0]),
        pool_root=pool_root,
        tier_enabled=tier_enabled,
        dedup_entitlement=entitlement,
    )


def run(st, context=None):
    verrors = ValidationErrors()
    failures = validate_set(context or RecordingContext(), st, verrors, logging.getLogger("test_set_rules"))
    return verrors, failures


def only(monkeypatch, *names):
    monkeypatch.setattr(set_rules, "SET_RULES", tuple(r for r in SET_RULES if r.check.__name__ in names))


def request(**kwargs):
    return ZFSResourceSetArgsData(path=PATH, **kwargs)


def request_errors(check, data):
    verrors = ValidationErrors()
    check(data, verrors)
    return [(e.attribute, e.errmsg) for e in verrors.errors]


def test_settable_properties():
    assert SETTABLE_PROPERTIES == SETTABLE


def test_non_inheritable_properties():
    assert NON_INHERITABLE_PROPERTIES == frozenset({"quota", "refquota", "reservation", "refreservation", "volsize"})
    assert INHERITABLE_PROPERTIES == SETTABLE - NON_INHERITABLE_PROPERTIES


def test_model_natives_are_the_settable_and_private_natives():
    assert MODEL_NATIVES == SETTABLE | PRIVATE_NATIVES


def test_set_read_properties():
    assert SET_READ_PROPERTIES == READ


def test_set_read_properties_avoid_names_with_their_own_read_cost():
    costly = {
        "casesensitivity",
        "normalization",
        "utf8only",
        "version",
        "clones",
        "mountpoint",
        "defaultuserquota",
        "defaultgroupquota",
        "defaultprojectquota",
        "defaultuserobjquota",
        "defaultgroupobjquota",
        "defaultprojectobjquota",
    }
    assert SET_READ_PROPERTIES.isdisjoint(costly)


def test_pool_root_inherit_values():
    assert dict(POOL_ROOT_INHERIT_VALUES) == {
        "acltype": "nfsv4",
        "aclmode": "discard",
        "aclinherit": "restricted",
        "dedup": "off",
        "special_small_blocks": 0,
    }
    assert set(POOL_ROOT_INHERIT_VALUES) <= INHERITABLE_PROPERTIES


def test_index_properties_are_settable():
    assert INDEX_PROPERTIES <= SETTABLE


RULE_TRIGGERS = {
    "check_names_valid_for_type": SETTABLE | PRIVATE_NATIVES,
    "check_inherit_not_received": SETTABLE | PRIVATE_NATIVES,
    "check_volsize_not_shrunk": {"volsize"},
    "check_volsize_multiple_of_volblocksize": {"volsize"},
    "check_reservation_headroom": {"volsize", "refreservation", "refquota"},
    "check_acl_combination": {"acltype", "aclmode"},
    "check_tier_managed_ssb": {"special_small_blocks"},
    "check_dedup_entitlement": {"dedup"},
    "check_dedup_tiering": {"dedup", "special_small_blocks"},
    "check_dedup_descendants": {"dedup"},
    "check_recordsize": {"recordsize"},
    "check_special_small_blocks_range": {"special_small_blocks"},
}


def test_set_rules_registry():
    assert [(r.check.__name__, r.triggers) for r in SET_RULES] == [
        (name, frozenset(triggers)) for name, triggers in RULE_TRIGGERS.items()
    ]


def test_property_view_miss_is_a_call_error():
    with pytest.raises(CallError) as ei:
        PropertyView(PATH, {"compression": "lz4"})["volsize"]
    assert ei.value.errmsg == "'volsize' was not read for 'tank/a'"


def test_property_view_value_without_a_reading_is_a_call_error():
    values = PropertyView(PATH, {"volsize": None})
    with pytest.raises(CallError):
        values["volsize"]
    assert values.get("volsize") is None


def test_has_work_rejects_an_empty_request():
    assert request_errors(check_has_work, request()) == [
        ("zfs.resource.set", "Nothing to update. Supply at least one of 'properties', 'user_properties' or 'inherit'.")
    ]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"properties": {"compression": "lz4"}},
        {"user_properties": {"org.truenas:x": "1"}},
        {"inherit": ["compression"]},
    ],
)
def test_has_work_accepts_each_half(kwargs):
    assert request_errors(check_has_work, request(**kwargs)) == []


def test_set_inherit_conflict_blames_each_name():
    data = request(
        properties={"compression": "lz4"},
        user_properties={"org.truenas:x": "1"},
        inherit=["compression", "org.truenas:x", "atime"],
    )
    assert [attribute for attribute, _ in request_errors(check_set_inherit_conflict, data)] == [
        "zfs.resource.set.inherit.compression",
        "zfs.resource.set.inherit.org.truenas:x",
    ]


@pytest.mark.parametrize("name", ["quota", "refquota", "reservation", "refreservation", "volsize"])
def test_inherit_of_a_property_without_an_inherited_value_is_rejected(name):
    assert request_errors(check_inherit_names, request(inherit=[name])) == [
        (f"zfs.resource.set.inherit.{name}", f"{name!r} has no inherited value.")
    ]


@pytest.mark.parametrize("name", ["mountpoint", "canmount", "casesensitivity", "bogus"])
def test_inherit_of_a_name_outside_the_settable_set_is_rejected(name):
    assert request_errors(check_inherit_names, request(inherit=[name])) == [
        (f"zfs.resource.set.inherit.{name}", f"{name!r} is not a settable property.")
    ]


@pytest.mark.parametrize("name", ["compression", "acltype", "org.truenas:custom"])
def test_inherit_accepts_inheritable_and_user_names(name):
    assert request_errors(check_inherit_names, request(inherit=[name])) == []


@pytest.mark.parametrize("name", ["ORG.Foo:x", "org.truenas:" + "x" * 250])
def test_inherit_of_a_bad_user_property_name_is_rejected(name):
    assert [attribute for attribute, _ in request_errors(check_inherit_names, request(inherit=[name]))] == [
        "zfs.resource.set.inherit"
    ]


@pytest.mark.parametrize(
    "user_properties, reason",
    [
        ({"ORG.Foo:x": "1"}, "may only contain lowercase letters"),
        ({"nocolon": "1"}, "must contain a colon"),
        ({"org.truenas:" + "x" * 245: "1"}, "must be shorter than 256 characters"),
        ({"org.truenas:x": "a\nb"}, "may not contain a line break"),
    ],
)
def test_bad_user_property_is_rejected(user_properties, reason):
    errors = request_errors(check_user_properties, request(user_properties=user_properties))
    assert len(errors) == 1
    assert errors[0][0] == "zfs.resource.set.user_properties"
    assert reason in errors[0][1]


def test_managed_user_property_is_accepted():
    data = request(user_properties={"org.freenas:quota_warning": "80"})
    assert request_errors(check_user_properties, data) == []


def test_request_rules_report_together():
    data = request(inherit=["volsize"], user_properties={"nocolon": "1"})
    assert [attribute for attribute, _ in request_errors(validate_request, data)] == [
        "zfs.resource.set.inherit.volsize",
        "zfs.resource.set.user_properties",
    ]


def test_effective_lowercases_a_requested_index_value():
    verrors, failures = run(state(properties={"dedup": "OFF"}, current={"dedup": "off"}, entitlement=DENIED))
    assert failures == []
    assert verrors.errors == []


def test_effective_keeps_the_case_of_a_requested_path():
    st = state(properties={"mountpoint": "/mnt/Tank/Data"})
    assert st.effective("mountpoint") == "/mnt/Tank/Data"


def test_inherited_aclmode_is_judged_by_the_parent_value():
    st = state(
        inherit=["aclmode"],
        current={"acltype": "posix", "aclmode": "discard"},
        parent={"aclmode": "passthrough"},
    )
    verrors, failures = run(st)
    assert failures == []
    assert [e.attribute for e in verrors.errors] == ["zfs.resource.set.inherit.aclmode"]


def test_inherited_aclmode_matching_a_requested_acltype_is_accepted():
    st = state(
        properties={"acltype": "nfsv4"},
        inherit=["aclmode"],
        current={"acltype": "posix", "aclmode": "discard"},
        parent={"aclmode": "passthrough"},
    )
    verrors, failures = run(st)
    assert failures == []
    assert verrors.errors == []


def test_pool_root_inherit_resolves_to_the_registered_default():
    st = state(
        inherit=["acltype"],
        current={"acltype": "posix", "aclmode": "passthrough"},
        pool_root=True,
        path="tank",
    )
    verrors, failures = run(st)
    assert failures == []
    assert verrors.errors == []


def test_pool_root_inherit_outside_the_default_table_is_a_call_error():
    st = state(inherit=["compression"], pool_root=True, path="tank")
    with pytest.raises(CallError) as ei:
        st.effective("compression")
    assert ei.value.errmsg == "'compression' has no source to inherit from on 'tank'"


SEMANTIC_CASES = {
    "check_names_valid_for_type": (
        dict(type_="VOLUME", properties={"atime": "off"}),
        {},
        "zfs.resource.set.properties.atime",
        "is not valid for a VOLUME",
    ),
    "check_inherit_not_received": (
        dict(inherit=["compression"], source="RECEIVED", parent={}),
        {},
        "zfs.resource.set.inherit.compression",
        "has a received value on",
    ),
    "check_volsize_not_shrunk": (
        dict(type_="VOLUME", properties={"volsize": 512 * MiB}, current={"volsize": GiB}),
        {},
        "zfs.resource.set.properties.volsize",
        "may not be reduced below the current size",
    ),
    "check_volsize_multiple_of_volblocksize": (
        dict(type_="VOLUME", properties={"volsize": GiB + 512}, current={"volsize": GiB, "volblocksize": 16384}),
        {},
        "zfs.resource.set.properties.volsize",
        "must be a multiple of the volblocksize",
    ),
    "check_reservation_headroom": (
        dict(type_="VOLUME", properties={"refreservation": 90 * GiB}),
        {},
        "zfs.resource.set.properties.refreservation",
        "would consume more than 80%",
    ),
    "check_acl_combination": (
        dict(properties={"acltype": "posix", "aclmode": "passthrough"}),
        {},
        "zfs.resource.set.properties.aclmode",
        "must be discard when the effective",
    ),
    "check_tier_managed_ssb": (
        dict(properties={"special_small_blocks": 262144}, tier_enabled=True),
        {},
        "zfs.resource.set.properties.special_small_blocks",
        "ZFS tiering is enabled",
    ),
    "check_dedup_entitlement": (
        dict(properties={"dedup": "on"}, entitlement=DENIED),
        {},
        "zfs.resource.set.properties.dedup",
        "SENTINEL entitlement denial",
    ),
    "check_dedup_tiering": (
        dict(properties={"dedup": "on"}, current={"special_small_blocks": 131072}, tier_enabled=True),
        {},
        "zfs.resource.set.properties.dedup",
        "cannot be enabled on a dataset assigned to",
    ),
    "check_dedup_descendants": (
        dict(properties={"dedup": "on"}, tier_enabled=True),
        {"descendants": [PERFORMANCE_CHILD]},
        "zfs.resource.set.properties.dedup",
        "cannot be enabled here: descendant dataset",
    ),
    "check_recordsize": (
        dict(properties={"recordsize": 3000}),
        {},
        "zfs.resource.set.properties.recordsize",
        "must be a power of two",
    ),
    "check_special_small_blocks_range": (
        dict(properties={"special_small_blocks": 32 * MiB}),
        {},
        "zfs.resource.set.properties.special_small_blocks",
        "'special_small_blocks' must be between",
    ),
}


@pytest.mark.parametrize("name", list(SEMANTIC_CASES))
def test_each_rule_reports_its_violation(name):
    kwargs, context, attribute, substring = SEMANTIC_CASES[name]
    verrors, failures = run(state(**kwargs), RecordingContext(**context))
    assert failures == []
    assert [(e.attribute, substring in e.errmsg) for e in verrors.errors] == [(attribute, True)]


def test_rule_messages_are_distinguishable(monkeypatch):
    messages = {}
    for name, (kwargs, context, _, _) in SEMANTIC_CASES.items():
        with monkeypatch.context() as m:
            only(m, name)
            verrors, _ = run(state(**kwargs), RecordingContext(**context))
        messages[name] = [e.errmsg for e in verrors.errors]
    for name, (_, _, _, substring) in SEMANTIC_CASES.items():
        for other, found in messages.items():
            assert any(substring in message for message in found) is (other == name), (name, other)


def test_acl_combination_blames_acltype_when_only_acltype_is_sent():
    verrors, _ = run(state(properties={"acltype": "posix"}, current={"aclmode": "passthrough"}))
    assert [e.attribute for e in verrors.errors] == ["zfs.resource.set.properties.acltype"]


def test_tier_rule_tolerates_setting_the_current_value():
    st = state(properties={"special_small_blocks": 131072}, current={"special_small_blocks": 131072}, tier_enabled=True)
    assert run(st)[0].errors == []


@pytest.mark.parametrize("source", ["INHERITED", "DEFAULT", "NONE"])
def test_tier_rule_tolerates_inheriting_a_value_that_is_not_local(source):
    st = state(inherit=["special_small_blocks"], source=source, parent={}, tier_enabled=True)
    assert run(st)[0].errors == []


def test_tier_rule_rejects_inheriting_a_local_value():
    st = state(inherit=["special_small_blocks"], parent={}, tier_enabled=True)
    assert [e.attribute for e in run(st)[0].errors] == ["zfs.resource.set.inherit.special_small_blocks"]


def test_inheriting_dedup_from_a_dedup_parent_needs_the_entitlement():
    st = state(inherit=["dedup"], parent={"dedup": "on"}, entitlement=DENIED)
    verrors, failures = run(st)
    assert failures == []
    assert [(e.attribute, e.errmsg) for e in verrors.errors] == [
        ("zfs.resource.set.inherit.dedup", "SENTINEL entitlement denial")
    ]


def test_setting_dedup_to_its_current_value_needs_no_entitlement():
    st = state(properties={"dedup": "on"}, current={"dedup": "on"}, entitlement=DENIED)
    assert run(st)[0].errors == []


def test_a_valid_request_reads_the_topology_and_the_descendants_and_passes():
    context = RecordingContext(
        special_vdev=True,
        draid=False,
        descendants=[
            descendant(f"{PATH}/local", 131072, "LOCAL"),
            descendant(f"{PATH}/regular", 0, "INHERITED", PATH),
        ],
    )
    st = state(properties={"dedup": "on", "recordsize": 65536}, tier_enabled=True)
    verrors, failures = run(st, context)
    assert failures == []
    assert verrors.errors == []
    assert context.calls == ["class_special_size", "zfs.resource.list_impl", "topology"]


def test_rules_report_together_in_registry_order():
    st = state(properties={"acltype": "posix", "aclmode": "passthrough", "dedup": "on"}, entitlement=DENIED)
    verrors, failures = run(st)
    assert failures == []
    assert [e.attribute for e in verrors.errors] == [
        "zfs.resource.set.properties.aclmode",
        "zfs.resource.set.properties.dedup",
    ]


def broken(context, state, verrors):
    raise KeyError("boom")


def reads_volsize(context, state, verrors):
    state.current["volsize"]


def raises_validation_error(context, state, verrors):
    raise ValidationError("zfs.resource.set.properties.compression", "raised, not added")


def test_a_broken_rule_is_returned_and_logged_while_the_others_report(monkeypatch, caplog):
    monkeypatch.setattr(
        set_rules,
        "SET_RULES",
        (SetRule(broken, frozenset({"compression"})), SetRule(check_acl_combination, frozenset({"acltype"}))),
    )
    st = state(properties={"compression": "gzip", "acltype": "posix"}, current={"aclmode": "passthrough"})
    with caplog.at_level(logging.ERROR):
        verrors, failures = run(st)
    assert [(name, type(error)) for name, error in failures] == [("broken", KeyError)]
    assert [e.attribute for e in verrors.errors] == ["zfs.resource.set.properties.acltype"]
    assert [r.getMessage() for r in caplog.records] == ["tank/a: rule broken failed"]


def test_a_property_view_miss_is_returned_as_a_failure(monkeypatch):
    monkeypatch.setattr(set_rules, "SET_RULES", (SetRule(reads_volsize, frozenset({"compression"})),))
    verrors, failures = run(state(properties={"compression": "gzip"}))
    assert [(name, type(error)) for name, error in failures] == [("reads_volsize", CallError)]
    assert verrors.errors == []


def test_a_raised_validation_error_is_collected(monkeypatch):
    monkeypatch.setattr(set_rules, "SET_RULES", (SetRule(raises_validation_error, frozenset({"compression"})),))
    verrors, failures = run(state(properties={"compression": "gzip"}))
    assert failures == []
    assert [(e.attribute, e.errmsg) for e in verrors.errors] == [
        ("zfs.resource.set.properties.compression", "raised, not added")
    ]


def raises_validation_errors(context, state, verrors):
    errors = ValidationErrors()
    errors.add("zfs.resource.set.properties.compression", "first")
    errors.add("zfs.resource.set.properties.atime", "second")
    raise errors


def test_raised_validation_errors_are_collected(monkeypatch):
    monkeypatch.setattr(set_rules, "SET_RULES", (SetRule(raises_validation_errors, frozenset({"compression"})),))
    verrors, failures = run(state(properties={"compression": "gzip"}))
    assert failures == []
    assert [(e.attribute, e.errmsg) for e in verrors.errors] == [
        ("zfs.resource.set.properties.compression", "first"),
        ("zfs.resource.set.properties.atime", "second"),
    ]


def test_inheriting_only_user_properties_runs_no_rule(monkeypatch):
    calls = []
    monkeypatch.setattr(set_rules, "SET_RULES", (SetRule(lambda *args: calls.append(args), MODEL_NATIVES),))
    st = state(inherit=["org.truenas:x"])
    assert st.touched() == frozenset()
    verrors, failures = run(st)
    assert (calls, failures, verrors.errors) == ([], [], [])


def test_acl_coupling_fills_the_companions_of_a_set_acltype_on_a_filesystem():
    st = apply_acl_coupling(state(properties={"acltype": "posix"}))
    assert (st.properties.aclmode, st.properties.aclinherit) == ("discard", "discard")
    assert st.derived == {"aclmode", "aclinherit"}


def test_acl_coupling_inherits_the_companions_of_an_inherited_acltype_on_a_filesystem():
    st = apply_acl_coupling(state(inherit=["acltype"], parent={}))
    assert st.inherit == {"acltype", "aclmode", "aclinherit"}
    assert st.derived == {"aclmode", "aclinherit"}


def test_acl_coupling_leaves_a_companion_the_caller_inherits():
    st = apply_acl_coupling(state(properties={"acltype": "posix"}, inherit=["aclmode"], parent={}))
    assert st.properties.aclmode is None
    assert st.inherit == {"aclmode"}
    assert st.derived == {"aclinherit"}


@pytest.mark.parametrize("kwargs", [{"properties": {"acltype": "posix"}}, {"inherit": ["acltype"]}])
def test_acl_coupling_adds_nothing_on_a_volume(kwargs):
    before = state(type_="VOLUME", **kwargs)
    after = apply_acl_coupling(before)
    assert (after.properties, after.inherit, after.derived) == (before.properties, before.inherit, frozenset())


def test_acltype_on_a_volume_is_one_error():
    verrors, failures = run(apply_acl_coupling(state(type_="VOLUME", properties={"acltype": "posix"})))
    assert failures == []
    assert [e.attribute for e in verrors.errors] == ["zfs.resource.set.properties.acltype"]


def test_pool_root_inherit_of_acltype_resolves_the_coupled_aclinherit_to_the_registered_default():
    st = state(inherit=["acltype"], current={"aclinherit": "passthrough"}, pool_root=True, path="tank")
    st = apply_acl_coupling(st)
    assert st.effective("aclinherit") == "restricted"


def test_acl_combination_blames_the_inherited_acltype_for_its_coupled_aclmode():
    st = apply_acl_coupling(
        state(
            inherit=["acltype"],
            current={"acltype": "nfsv4", "aclmode": "passthrough"},
            parent={"acltype": "posix", "aclmode": "passthrough"},
        )
    )
    verrors, failures = run(st)
    assert failures == []
    assert [e.attribute for e in verrors.errors] == ["zfs.resource.set.inherit.acltype"]


def test_inherit_of_a_received_acltype_is_rejected():
    st = state(inherit=["acltype"], source="RECEIVED", parent={}, current={"aclmode": "passthrough"})
    verrors, failures = run(st)
    assert failures == []
    assert [(e.attribute, "has a received value on 'tank/a'" in e.errmsg) for e in verrors.errors] == [
        ("zfs.resource.set.inherit.acltype", True)
    ]


def volume(properties, refreservation, volsize=GiB, source="LOCAL", **current):
    return state(
        type_="VOLUME",
        properties=properties,
        current={"volsize": volsize, "refreservation": refreservation, **current},
        source=source,
    )


@pytest.mark.parametrize(
    "refreservation, volsize",
    [
        (GiB, 2 * GiB),
        (GiB + 32 * MiB, 2 * GiB),
        (GiB + 512 * MiB, 2 * GiB),
    ],
    ids=["exact", "canonical", "outrun-over-reservation"],
)
def test_thick_follow_re_reserves_a_grow_the_reservation_no_longer_covers(refreservation, volsize):
    st = apply_thick_follow(volume({"volsize": volsize}, refreservation))
    assert st.properties.refreservation == "auto"
    assert st.derived == {"refreservation"}


@pytest.mark.parametrize(
    "properties, refreservation, source",
    [
        ({"volsize": 2 * GiB}, 5 * GiB, "LOCAL"),
        ({"volsize": GiB + 16 * MiB}, GiB + 32 * MiB, "LOCAL"),
        ({"volsize": 2 * GiB}, 0, "LOCAL"),
        ({"volsize": 2 * GiB}, 512 * MiB, "LOCAL"),
        ({"volsize": 2 * GiB, "refreservation": 3 * GiB}, GiB, "LOCAL"),
        ({"volsize": 512 * MiB}, GiB, "LOCAL"),
        ({"volsize": 2 * GiB}, GiB, "RECEIVED"),
    ],
    ids=["over-reserved", "still-covering", "sparse", "partial", "explicit", "shrink", "received"],
)
def test_thick_follow_leaves_the_reservation_alone(properties, refreservation, source):
    st = apply_thick_follow(volume(properties, refreservation, source=source))
    assert st.properties.refreservation == properties.get("refreservation")
    assert st.derived == frozenset()


def test_thick_follow_does_not_touch_a_filesystem():
    st = apply_thick_follow(state(properties={"volsize": 2 * GiB}, current={"refreservation": GiB}))
    assert (st.properties.refreservation, st.derived) == (None, frozenset())


def headroom_errors(st):
    verrors, failures = run(st)
    assert failures == []
    return [(e.attribute, e.errmsg) for e in verrors.errors]


def test_headroom_of_a_followed_grow_blames_volsize():
    st = apply_thick_follow(volume({"volsize": 100 * GiB}, GiB, available=50 * GiB))
    [(attribute, errmsg)] = headroom_errors(st)
    assert attribute == "zfs.resource.set.properties.volsize"
    assert "would consume more than 80%" in errmsg


def test_headroom_of_an_explicit_refreservation_blames_refreservation():
    st = apply_thick_follow(volume({"volsize": 100 * GiB, "refreservation": 100 * GiB}, GiB, available=50 * GiB))
    assert [attribute for attribute, _ in headroom_errors(st)] == ["zfs.resource.set.properties.refreservation"]


def test_headroom_escape_is_an_explicit_zero_refreservation():
    st = apply_thick_follow(volume({"volsize": 2 * GiB, "refreservation": 0}, GiB, available=MiB))
    assert headroom_errors(st) == []


def test_headroom_rejects_auto_on_a_filesystem():
    st = state(properties={"refreservation": "auto"})
    assert headroom_errors(st) == [("zfs.resource.set.properties.refreservation", "'auto' is only valid on volumes.")]


@pytest.mark.parametrize("usedbyrefreservation, rejected", [(100 * GiB, True), (0, False)])
def test_headroom_base_excludes_the_space_the_reservation_itself_holds(usedbyrefreservation, rejected):
    st = volume(
        {"refreservation": 100 * GiB},
        10 * GiB,
        available=200 * GiB,
        usedbyrefreservation=usedbyrefreservation,
    )
    assert bool(headroom_errors(st)) is rejected


def test_headroom_rejects_a_filesystem_refreservation_over_its_refquota():
    st = state(properties={"refreservation": 2 * GiB}, current={"refquota": GiB, "available": GiB})
    assert headroom_errors(st) == [
        (
            "zfs.resource.set.properties.refreservation",
            f"A refreservation of {2 * GiB} exceeds the refquota of {GiB} on 'tank/a'.",
        )
    ]


def test_headroom_judges_a_filesystem_refreservation_against_the_requested_refquota():
    st = state(properties={"refreservation": 2 * GiB, "refquota": 3 * GiB}, current={"refquota": GiB, "available": GiB})
    assert headroom_errors(st) == []


def test_headroom_is_exact_when_a_refquota_is_introduced_in_the_request():
    st = state(
        properties={"refreservation": 2 * GiB, "refquota": 3 * GiB},
        current={"refquota": 0, "available": 2 * GiB},
    )
    [(attribute, errmsg)] = headroom_errors(st)
    assert attribute == "zfs.resource.set.properties.refreservation"
    assert "would consume more than 80%" in errmsg


def test_headroom_is_skipped_when_the_request_drops_the_refquota():
    st = state(properties={"refreservation": 2 * GiB, "refquota": 0}, current={"refquota": GiB, "available": GiB})
    assert headroom_errors(st) == []


def test_headroom_reports_both_kernel_legs_on_an_unclamped_filesystem():
    st = state(
        properties={"refreservation": 4 * GiB, "refquota": 3 * GiB},
        current={"refquota": 0, "available": 2 * GiB},
    )
    [(refquota_attribute, refquota), (headroom_attribute, headroom)] = sorted(headroom_errors(st), key=lambda e: e[1])
    assert headroom_attribute == refquota_attribute == "zfs.resource.set.properties.refreservation"
    assert refquota == f"A refreservation of {4 * GiB} exceeds the refquota of {3 * GiB} on 'tank/a'."
    assert "would consume more than 80%" in headroom


def test_headroom_of_a_thick_grow_does_not_read_refquota_on_a_volume():
    st = apply_thick_follow(volume({"volsize": 2 * GiB}, GiB))
    assert "refquota" not in st.current
    assert headroom_errors(st) == []


def test_dedup_descendants_names_only_the_descendants_that_would_inherit_it():
    context = RecordingContext(
        descendants=[
            descendant(f"{PATH}/from_ancestor", 131072, "INHERITED", "tank"),
            descendant(f"{PATH}/local", 131072, "LOCAL"),
            descendant(f"{PATH}/regular", 0, "DEFAULT"),
            descendant(f"{PATH}/mid/leaf", 131072, "INHERITED", f"{PATH}/mid"),
            descendant(f"{PATH}/vol", 131072, "DEFAULT", type_="VOLUME"),
        ]
    )
    verrors, failures = run(state(properties={"dedup": "on"}, tier_enabled=True), context)
    assert failures == []
    [error] = verrors.errors
    assert "descendant dataset 'tank/a/from_ancestor' is assigned" in error.errmsg


def test_dedup_descendants_counts_every_affected_descendant():
    context = RecordingContext(
        descendants=[
            descendant(f"{PATH}/b", 131072, "DEFAULT"),
            descendant(f"{PATH}/c", 131072, "INHERITED", PATH),
        ]
    )
    [error] = run(state(properties={"dedup": "on"}, tier_enabled=True), context)[0].errors
    assert "descendant dataset 'tank/a/b' (and 1 more) is assigned" in error.errmsg


def test_dedup_descendants_skips_the_walk_without_a_special_vdev():
    context = RecordingContext(special_vdev=False, descendants=[PERFORMANCE_CHILD])
    verrors, failures = run(state(properties={"dedup": "on"}, tier_enabled=True), context)
    assert (verrors.errors, failures) == ([], [])
    assert "zfs.resource.list_impl" not in context.calls


def recordsize_errors(recordsize, context=None):
    verrors, failures = run(state(properties={"recordsize": recordsize}), context)
    assert failures == []
    return [e.errmsg for e in verrors.errors]


def test_recordsize_above_the_module_maximum_is_rejected(max_recordsize):
    max_recordsize.write_text(f"{MiB}\n")
    assert recordsize_errors(2 * MiB) == [f"'recordsize' must be a power of two from 512 to {MiB} bytes."]
    assert recordsize_errors(MiB) == []


def test_recordsize_is_capped_at_the_largest_block_size(max_recordsize):
    max_recordsize.write_text(f"{64 * MiB}\n")
    assert recordsize_errors(32 * MiB) == [f"'recordsize' must be a power of two from 512 to {16 * MiB} bytes."]


def test_recordsize_below_512_is_rejected():
    assert recordsize_errors(256) == [f"'recordsize' must be a power of two from 512 to {16 * MiB} bytes."]


@pytest.mark.parametrize(
    "draid, errors", [(True, ["'recordsize' must be at least 131072 bytes on a dRAID pool."]), (False, [])]
)
def test_small_recordsize_is_rejected_only_on_draid(draid, errors):
    assert recordsize_errors(65536, RecordingContext(draid=draid)) == errors


def test_special_small_blocks_range_includes_the_largest_block_size():
    verrors, failures = run(state(properties={"special_small_blocks": 16 * MiB}))
    assert (verrors.errors, failures) == ([], [])


TYPES = ("FILESYSTEM", "VOLUME")
VARIANTS = ("set", "inherit", "pool_root")
CELL_FIXTURES = {
    "check_names_valid_for_type": {
        "current": {},
        "request": EVERY_NATIVE,
        "parent": {},
        "pool_current": {},
        "substring": "is not valid for a",
    },
    "check_inherit_not_received": {
        "current": {},
        "request": EVERY_NATIVE,
        "parent": {},
        "pool_current": {},
        "source": "RECEIVED",
        "substring": "has a received value",
    },
    "check_volsize_not_shrunk": {
        "current": {"volsize": GiB},
        "request": {"volsize": 512},
        "parent": {},
        "pool_current": {"volsize": GiB},
        "substring": "may not be reduced",
    },
    "check_volsize_multiple_of_volblocksize": {
        "current": {"volsize": GiB, "volblocksize": 16384},
        "request": {"volsize": GiB + 512},
        "parent": {},
        "pool_current": {"volsize": GiB, "volblocksize": 16384},
        "substring": "must be a multiple of the volblocksize",
    },
    "check_reservation_headroom": {
        "current": {
            "volsize": GiB,
            "refreservation": GiB,
            "available": 10 * GiB,
            "usedbyrefreservation": 0,
        },
        "request": {"volsize": 2 * GiB, "refreservation": 50 * GiB, "refquota": GiB},
        "parent": {},
        "pool_current": {"volsize": GiB, "refreservation": GiB, "available": 10 * GiB, "refquota": 2 * GiB},
        "substring": "Reserving another",
    },
    "check_acl_combination": {
        "current": {"acltype": "posix", "aclmode": "passthrough"},
        "request": {"acltype": "posix", "aclmode": "passthrough"},
        "parent": {"acltype": "posix", "aclmode": "passthrough"},
        "pool_current": {"acltype": "nfsv4", "aclmode": "discard"},
        "substring": "'aclmode'",
    },
    "check_tier_managed_ssb": {
        "current": {"special_small_blocks": 131072},
        "request": {"special_small_blocks": 262144},
        "parent": {"special_small_blocks": 262144},
        "pool_current": {"special_small_blocks": 131072},
        "substring": "ZFS tiering is enabled",
    },
    "check_dedup_entitlement": {
        "current": {"dedup": "on"},
        "request": {"dedup": "verify"},
        "parent": {"dedup": "verify"},
        "pool_current": {"dedup": "on"},
        "substring": "SENTINEL entitlement denial",
    },
    "check_dedup_tiering": {
        "current": {"dedup": "on", "special_small_blocks": 131072},
        "request": {"dedup": "verify", "special_small_blocks": 262144},
        "parent": {"dedup": "verify", "special_small_blocks": 262144},
        "pool_current": {"dedup": "on", "special_small_blocks": 131072},
        "substring": "cannot be enabled on a dataset assigned to",
    },
    "check_dedup_descendants": {
        "current": {"dedup": "off"},
        "request": {"dedup": "on"},
        "parent": {"dedup": "on"},
        "pool_current": {"dedup": "on"},
        "substring": "cannot be enabled here: descendant dataset",
    },
    "check_recordsize": {
        "current": {"recordsize": 131072},
        "request": {"recordsize": 3000},
        "parent": {"recordsize": 3000},
        "pool_current": {"recordsize": 131072},
        "substring": "must be a power of two",
    },
    "check_special_small_blocks_range": {
        "current": {"special_small_blocks": 0},
        "request": {"special_small_blocks": 32 * MiB},
        "parent": {"special_small_blocks": 32 * MiB},
        "pool_current": {"special_small_blocks": 0},
        "substring": "'special_small_blocks' must be between",
    },
}
VIOLATION_CONSTRUCTIBLE = {
    ("check_volsize_not_shrunk", "VOLUME", "set"),
    ("check_volsize_multiple_of_volblocksize", "VOLUME", "set"),
    *(("check_acl_combination", "FILESYSTEM", variant) for variant in VARIANTS),
    *(("check_tier_managed_ssb", type_, variant) for type_ in TYPES for variant in VARIANTS),
    *(("check_dedup_entitlement", type_, variant) for type_ in TYPES for variant in ("set", "inherit")),
    *(("check_dedup_tiering", "FILESYSTEM", variant) for variant in ("set", "inherit")),
    *(("check_dedup_descendants", "FILESYSTEM", variant) for variant in ("set", "inherit")),
    ("check_recordsize", "FILESYSTEM", "set"),
    *(("check_special_small_blocks_range", type_, "set") for type_ in TYPES),
}
VALID_NATIVES = {"FILESYSTEM": FILESYSTEM_NATIVES, "VOLUME": VOLUME_NATIVES}
READ_NAMES = {"FILESYSTEM": FILESYSTEM_NAMES, "VOLUME": VOLUME_NAMES}


def violation_constructible(name, type_, variant, names):
    if name == "check_names_valid_for_type":
        return bool(names - VALID_NATIVES[type_])
    if name == "check_inherit_not_received":
        return variant != "set" and bool(names & READ_NAMES[type_])
    if name == "check_reservation_headroom":
        return variant == "set" and "refreservation" in names
    return (name, type_, variant) in VIOLATION_CONSTRUCTIBLE


def cells():
    for name, triggers in RULE_TRIGGERS.items():
        subsets = {frozenset({trigger}) for trigger in triggers} | {frozenset(triggers)}
        for names in sorted(subsets, key=sorted):
            for type_ in TYPES:
                for variant in VARIANTS:
                    label = "ALL" if len(names) > 3 else "+".join(sorted(names))
                    yield pytest.param(name, type_, variant, names, id=f"{name}-{type_}-{variant}-{label}")


@pytest.mark.parametrize("name, type_, variant, names", list(cells()))
def test_rule_reads_only_what_its_type_gate_guarantees(monkeypatch, caplog, name, type_, variant, names):
    fixture = CELL_FIXTURES[name]
    common = dict(type_=type_, tier_enabled=True, entitlement=DENIED, source=fixture.get("source", "LOCAL"))
    if variant == "set":
        st = state(properties={n: fixture["request"][n] for n in names}, current=fixture["current"], **common)
    elif variant == "inherit":
        st = state(inherit=names, current=fixture["current"], parent=fixture["parent"], **common)
    else:
        st = state(inherit=names, current=fixture["pool_current"], pool_root=True, path="tank", **common)
    only(monkeypatch, name)
    with caplog.at_level(logging.ERROR):
        verrors, failures = run(st, RecordingContext(descendants=[PERFORMANCE_CHILD]))
    assert failures == []
    assert caplog.records == []
    if violation_constructible(name, type_, variant, names):
        assert any(fixture["substring"] in e.errmsg for e in verrors.errors)
    else:
        assert verrors.errors == []
