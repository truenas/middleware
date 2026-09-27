from types import SimpleNamespace

import pytest

from middlewared.api.current import ZFSResourceSetProperties
from middlewared.plugins.zfs import set_rules
from middlewared.plugins.zfs.set_rules import (
    SET_READ_PROPERTIES,
    PropertyView,
    SetContext,
    apply_acl_coupling,
    apply_thick_follow,
    validate_set,
)
from middlewared.service_exception import ValidationErrors

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


READ = SETTABLE | {"available", "keystatus", "volblocksize", "usedbyrefreservation"}


FILESYSTEM_NAMES = READ - {"volsize", "volblocksize"}


VOLUME_NAMES = frozenset(
    {
        "available",
        "checksum",
        "compression",
        "copies",
        "dedup",
        "keystatus",
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
    "keystatus": None,
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


DENIED = SimpleNamespace(entitled=False, message="SENTINEL entitlement denial")


ALLOWED = SimpleNamespace(entitled=True, message="")


@pytest.fixture(autouse=True)
def type_masks(monkeypatch):
    monkeypatch.setattr(set_rules, "ZFSProperty", {name.upper(): name for name in SETTABLE | PRIVATE_NATIVES})
    monkeypatch.setattr(set_rules, "PROPERTY_TEMPLATES", SimpleNamespace(fs=FILESYSTEM_NATIVES, vol=VOLUME_NATIVES))


def descendant(name, ssb, dedup_source, inherited_from=None, type_="FILESYSTEM"):
    return {
        "name": name,
        "type": type_,
        "properties": {
            "dedup": {"value": "off", "source": {"type": dedup_source, "value": inherited_from}},
            "special_small_blocks": {"value": ssb, "source": {"type": "LOCAL", "value": None}},
        },
    }


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
    validate_set(context or RecordingContext(), st, verrors)
    return verrors


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


@pytest.mark.parametrize("source", ["INHERITED", "DEFAULT"])
def test_tier_rule_tolerates_inheriting_a_value_that_is_not_local(source):
    st = state(inherit=["special_small_blocks"], source=source, parent={}, tier_enabled=True)
    assert run(st).errors == []


def test_setting_dedup_to_its_current_value_needs_no_entitlement():
    st = state(properties={"dedup": "on"}, current={"dedup": "on"}, entitlement=DENIED)
    assert run(st).errors == []


def test_acl_coupling_leaves_a_companion_the_caller_inherits():
    st = apply_acl_coupling(state(properties={"acltype": "posix"}, inherit=["aclmode"], parent={}))
    assert st.properties.aclmode is None
    assert st.inherit == {"aclmode"}
    assert st.derived == {"aclinherit"}


def volume(properties, refreservation, volsize=GiB, source="LOCAL", **current):
    return state(
        type_="VOLUME",
        properties=properties,
        current={"volsize": volsize, "refreservation": refreservation, **current},
        source=source,
    )


@pytest.mark.parametrize(
    "properties, refreservation, source",
    [({"volsize": 2 * GiB}, GiB, "RECEIVED")],
    ids=["received"],
)
def test_thick_follow_leaves_the_reservation_alone(properties, refreservation, source):
    st = apply_thick_follow(volume(properties, refreservation, source=source))
    assert st.properties.refreservation == properties.get("refreservation")
    assert st.derived == frozenset()


def headroom_errors(st):
    return [(e.attribute, e.errmsg) for e in run(st).errors]


@pytest.mark.parametrize("usedbyrefreservation, rejected", [(100 * GiB, True), (0, False)])
def test_headroom_base_excludes_the_space_the_reservation_itself_holds(usedbyrefreservation, rejected):
    st = volume(
        {"refreservation": 100 * GiB},
        10 * GiB,
        available=200 * GiB,
        usedbyrefreservation=usedbyrefreservation,
    )
    assert bool(headroom_errors(st)) is rejected


def test_headroom_is_exact_when_a_refquota_is_introduced_in_the_request():
    st = state(
        properties={"refreservation": 2 * GiB, "refquota": 3 * GiB},
        current={"refquota": 0, "available": 2 * GiB},
    )
    [(attribute, errmsg)] = headroom_errors(st)
    assert attribute == "zfs.resource.set.properties.refreservation"
    assert "would consume more than 80%" in errmsg


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
    verrors = run(state(properties={"dedup": "on"}, tier_enabled=True), context)
    [error] = verrors.errors
    assert "descendant dataset 'tank/a/from_ancestor' is assigned" in error.errmsg


def test_special_small_blocks_range_includes_the_largest_block_size():
    assert run(state(properties={"special_small_blocks": 16 * MiB})).errors == []


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(properties={"compression": "gzip"}, current={"acltype": "posix", "aclmode": "passthrough"}),
        dict(properties={"compression": "gzip"}, tier_enabled=True, current={"special_small_blocks": 131072}),
    ],
)
def test_rules_gated_on_their_trigger_ignore_untouched_state(kwargs):
    assert run(state(**kwargs)).errors == []
