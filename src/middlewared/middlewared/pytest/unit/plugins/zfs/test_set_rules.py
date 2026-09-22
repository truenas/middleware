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
    check_acl_combination,
    check_has_work,
    check_inherit_names,
    check_set_inherit_conflict,
    check_user_properties,
    validate_request,
    validate_set,
)
from middlewared.service_exception import CallError, ValidationError, ValidationErrors

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
DENIED = SimpleNamespace(entitled=False, message="SENTINEL entitlement denial")
ALLOWED = SimpleNamespace(entitled=True, message="")


class RecordingContext:
    def __init__(self, special_vdev=True):
        self.special_vdev = special_vdev
        self.calls = []
        self.middleware = SimpleNamespace(call_sync=self.call_sync)

    def call_sync(self, method, *args):
        self.calls.append(method)
        if method == "zpool.query_impl":
            return [{"properties": {"class_special_size": {"value": GiB if self.special_vdev else 0}}}]
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
    "check_volsize_not_shrunk": {"volsize"},
    "check_acl_combination": {"acltype", "aclmode"},
    "check_tier_managed_ssb": {"special_small_blocks"},
    "check_dedup_entitlement": {"dedup"},
    "check_dedup_tiering": {"dedup", "special_small_blocks"},
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
    "check_volsize_not_shrunk": (
        dict(type_="VOLUME", properties={"volsize": 512}, current={"volsize": GiB}),
        "zfs.resource.set.properties.volsize",
        "may not be reduced below the current size",
    ),
    "check_acl_combination": (
        dict(properties={"acltype": "posix", "aclmode": "passthrough"}),
        "zfs.resource.set.properties.aclmode",
        "must be discard when the effective",
    ),
    "check_tier_managed_ssb": (
        dict(properties={"special_small_blocks": 262144}, tier_enabled=True),
        "zfs.resource.set.properties.special_small_blocks",
        "ZFS tiering is enabled",
    ),
    "check_dedup_entitlement": (
        dict(properties={"dedup": "on"}, entitlement=DENIED),
        "zfs.resource.set.properties.dedup",
        "SENTINEL entitlement denial",
    ),
    "check_dedup_tiering": (
        dict(properties={"dedup": "on"}, current={"special_small_blocks": 131072}, tier_enabled=True),
        "zfs.resource.set.properties.dedup",
        "cannot be enabled on a dataset assigned to",
    ),
}


@pytest.mark.parametrize("name", list(SEMANTIC_CASES))
def test_each_rule_reports_its_violation(name):
    kwargs, attribute, substring = SEMANTIC_CASES[name]
    verrors, failures = run(state(**kwargs))
    assert failures == []
    assert [(e.attribute, substring in e.errmsg) for e in verrors.errors] == [(attribute, True)]


def test_rule_messages_are_distinguishable(monkeypatch):
    messages = {}
    for name, (kwargs, _, _) in SEMANTIC_CASES.items():
        with monkeypatch.context() as m:
            only(m, name)
            verrors, _ = run(state(**kwargs))
        messages[name] = [e.errmsg for e in verrors.errors]
    for name, (_, _, substring) in SEMANTIC_CASES.items():
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


def test_a_valid_request_reads_the_topology_and_passes():
    context = RecordingContext(special_vdev=False)
    st = state(properties={"dedup": "on"}, current={"special_small_blocks": 131072}, tier_enabled=True)
    verrors, failures = run(st, context)
    assert failures == []
    assert verrors.errors == []
    assert context.calls == ["zpool.query_impl"]


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


TYPES = ("FILESYSTEM", "VOLUME")
VARIANTS = ("set", "inherit", "pool_root")
CELL_FIXTURES = {
    "check_volsize_not_shrunk": {
        "current": {"volsize": GiB},
        "request": {"volsize": 512},
        "parent": {},
        "pool_current": {"volsize": GiB},
        "substring": "may not be reduced",
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
}
VIOLATION_CONSTRUCTIBLE = {
    ("check_volsize_not_shrunk", "VOLUME", "set"),
    *(("check_acl_combination", "FILESYSTEM", variant) for variant in VARIANTS),
    *(("check_tier_managed_ssb", type_, variant) for type_ in TYPES for variant in VARIANTS),
    *(("check_dedup_entitlement", type_, variant) for type_ in TYPES for variant in ("set", "inherit")),
    *(("check_dedup_tiering", "FILESYSTEM", variant) for variant in ("set", "inherit")),
}


def cells():
    for name, triggers in RULE_TRIGGERS.items():
        subsets = {frozenset({trigger}) for trigger in triggers} | {frozenset(triggers)}
        for names in sorted(subsets, key=sorted):
            for type_ in TYPES:
                for variant in VARIANTS:
                    yield pytest.param(
                        name, type_, variant, names, id=f"{name}-{type_}-{variant}-{'+'.join(sorted(names))}"
                    )


@pytest.mark.parametrize("name, type_, variant, names", list(cells()))
def test_rule_reads_only_what_its_type_gate_guarantees(monkeypatch, caplog, name, type_, variant, names):
    fixture = CELL_FIXTURES[name]
    common = dict(type_=type_, tier_enabled=True, entitlement=DENIED)
    if variant == "set":
        st = state(properties={n: fixture["request"][n] for n in names}, current=fixture["current"], **common)
    elif variant == "inherit":
        st = state(inherit=names, current=fixture["current"], parent=fixture["parent"], **common)
    else:
        st = state(inherit=names, current=fixture["pool_current"], pool_root=True, path="tank", **common)
    only(monkeypatch, name)
    with caplog.at_level(logging.ERROR):
        verrors, failures = run(st)
    assert failures == []
    assert caplog.records == []
    if (name, type_, variant) in VIOLATION_CONSTRUCTIBLE:
        assert any(fixture["substring"] in e.errmsg for e in verrors.errors)
    else:
        assert verrors.errors == []
