import errno
import logging
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from middlewared.api.current import ZFSResourceCreateArgsData
from middlewared.plugins.zfs import resource_create
from middlewared.plugins.zfs.create_rules import (
    CreateContext,
    apply_draid_volblocksize,
    check_acl_combination,
    check_dedup_entitlement,
    check_dedup_tiering,
    check_encryption,
    check_name_valid,
    check_parent_is_filesystem,
    check_parent_not_readonly,
    check_volume_capacity,
    check_volume_has_volsize,
)
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service import ServiceContext
from middlewared.service_exception import ValidationErrors

GiB = 1024**3
SCHEMA = "zfs.resource.create"


def request(path="tank/new", **kwargs):
    return ZFSResourceCreateArgsData(path=path, **kwargs)


def context_for(data, ancestors=(), encrypt=None, **kwargs):
    return CreateContext(
        properties=data.properties.model_copy(),
        encrypt=encrypt,
        ancestors={row["name"]: row for row in ancestors},
        **kwargs,
    )


def row(name, type_="FILESYSTEM", **props):
    return {
        "name": name,
        "type": type_,
        "properties": {key: {"raw": str(value), "value": value} for key, value in props.items()},
    }


def service_context(zpool_query_impl=None):
    middleware = Middleware()
    middleware["zpool.query_impl"] = zpool_query_impl or (lambda args: [])
    return ServiceContext(middleware, logging.getLogger("test"))


def errors_of(verrors):
    return [(e.attribute, e.errmsg) for e in verrors.errors]


def assert_one_error(verrors, attribute, fragment):
    [(got_attribute, errmsg)] = errors_of(verrors)
    assert got_attribute == attribute
    assert fragment in errmsg


def test_name_with_trailing_space_is_rejected():
    data = request(path="tank/new ")
    verrors = ValidationErrors()
    check_name_valid(data, context_for(data), verrors)
    assert_one_error(verrors, SCHEMA, "Trailing spaces are not permitted")


def test_valid_name_is_accepted():
    data = request()
    verrors = ValidationErrors()
    check_name_valid(data, context_for(data), verrors)
    assert not verrors


def test_volume_without_volsize_is_rejected():
    data = request(type="VOLUME")
    verrors = ValidationErrors()
    check_volume_has_volsize(data, context_for(data), verrors)
    assert_one_error(verrors, f"{SCHEMA}.properties", "'volsize' is required")


def test_volume_with_volsize_is_accepted():
    data = request(type="VOLUME", properties={"volsize": GiB})
    verrors = ValidationErrors()
    check_volume_has_volsize(data, context_for(data), verrors)
    assert not verrors


def test_volume_parent_is_rejected():
    data = request(path="tank/vol/new")
    verrors = ValidationErrors()
    check_parent_is_filesystem(data, context_for(data, [row("tank/vol", "VOLUME"), row("tank")]), verrors)
    assert_one_error(verrors, SCHEMA, "'tank/vol' is a volume and cannot hold 'tank/vol/new'.")


def test_filesystem_parent_is_accepted():
    data = request(path="tank/fs/new")
    verrors = ValidationErrors()
    check_parent_is_filesystem(data, context_for(data, [row("tank/fs"), row("tank")]), verrors)
    assert not verrors


def test_readonly_parent_is_rejected():
    data = request()
    verrors = ValidationErrors()
    check_parent_not_readonly(data, context_for(data, [row("tank", readonly="on")]), verrors)
    assert_one_error(verrors, SCHEMA, "Turn off readonly mode on 'tank'")


def test_writable_parent_is_accepted():
    data = request()
    verrors = ValidationErrors()
    check_parent_not_readonly(data, context_for(data, [row("tank", readonly="off")]), verrors)
    assert not verrors


def test_unentitled_dedup_is_rejected():
    data = request(properties={"dedup": "on"})
    entitlement = SimpleNamespace(entitled=False, message="sentinel entitlement message")
    verrors = ValidationErrors()
    check_dedup_entitlement(data, context_for(data, dedup_entitlement=entitlement), verrors)
    assert_one_error(verrors, f"{SCHEMA}.properties", "sentinel entitlement message")


def test_entitled_dedup_is_accepted():
    data = request(properties={"dedup": "on"})
    entitlement = SimpleNamespace(entitled=True, message="sentinel entitlement message")
    verrors = ValidationErrors()
    check_dedup_entitlement(data, context_for(data, dedup_entitlement=entitlement), verrors)
    assert not verrors


def special_vdev_pool(args):
    return [{"properties": {"class_special_size": {"value": GiB}}}]


def test_dedup_on_performance_tier_is_rejected():
    data = request(properties={"dedup": "on"})
    verrors = ValidationErrors()
    ctx = context_for(data, [row("tank", special_small_blocks=16 * 1024**2)])
    check_dedup_tiering(service_context(special_vdev_pool), data, ctx, verrors)
    assert_one_error(verrors, f"{SCHEMA}.properties", "cannot be enabled on a dataset assigned to")


def test_dedup_on_regular_tier_is_accepted():
    data = request(properties={"dedup": "on"})
    verrors = ValidationErrors()
    ctx = context_for(data, [row("tank", special_small_blocks=0)])
    check_dedup_tiering(service_context(special_vdev_pool), data, ctx, verrors)
    assert not verrors


def test_posix_acltype_with_passthrough_aclmode_is_rejected():
    data = request(properties={"acltype": "posix", "aclmode": "passthrough"})
    verrors = ValidationErrors()
    check_acl_combination(data, context_for(data), verrors)
    assert_one_error(verrors, f"{SCHEMA}.properties", "'aclmode' must be discard")


def test_posix_acltype_with_discard_aclmode_is_accepted():
    data = request(properties={"acltype": "posix", "aclmode": "discard"})
    verrors = ValidationErrors()
    check_acl_combination(data, context_for(data), verrors)
    assert not verrors


def thick_volume():
    return request(path="tank/vol", type="VOLUME", properties={"volsize": GiB, "refreservation": GiB})


def test_reservation_over_the_space_left_to_a_child_is_rejected():
    data = thick_volume()
    verrors = ValidationErrors()
    ancestor = row("tank", available=2 * GiB, usedbyrefreservation=GiB)
    check_volume_capacity(data, context_for(data, [ancestor]), verrors)
    assert_one_error(verrors, f"{SCHEMA}.properties.refreservation", "would consume more than 80%")


def test_reservation_within_the_space_left_to_a_child_is_accepted():
    data = thick_volume()
    verrors = ValidationErrors()
    ancestor = row("tank", available=2 * GiB, usedbyrefreservation=0)
    check_volume_capacity(data, context_for(data, [ancestor]), verrors)
    assert not verrors


def test_encryption_without_key_material_is_rejected():
    data = request(encryption={})
    verrors = ValidationErrors()
    check_encryption(data, context_for(data, [row("tank", encryption="off")]), verrors)
    assert_one_error(verrors, f"{SCHEMA}.encryption", "Exactly one of")


def test_encryption_with_one_key_source_is_accepted():
    data = request(encryption={"generate_key": True})
    verrors = ValidationErrors()
    encrypt = {"keyformat": "hex", "key": "0" * 64}
    check_encryption(data, context_for(data, [row("tank", encryption="off")], encrypt=encrypt), verrors)
    assert not verrors


def draid_pool(args):
    return [{"topology": {"data": [{"vdev_type": "draid1:1d:2c:0s"}]}}]


def test_small_volblocksize_on_draid_is_rejected():
    data = request(type="VOLUME", properties={"volsize": GiB, "volblocksize": 16384})
    verrors = ValidationErrors()
    apply_draid_volblocksize(service_context(draid_pool), data, context_for(data), verrors)
    assert_one_error(verrors, f"{SCHEMA}.properties", "greater than or equal to 32K")


def test_large_volblocksize_on_draid_is_accepted():
    data = request(type="VOLUME", properties={"volsize": GiB, "volblocksize": 32768})
    verrors = ValidationErrors()
    apply_draid_volblocksize(service_context(draid_pool), data, context_for(data), verrors)
    assert not verrors


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
        self.context = ServiceContext(middleware, logging.getLogger("test"))
        monkeypatch.setattr(resource_create, "_raw_create", self.raw_create)

    def zpool_query_impl(self, args):
        self.zpool_reads.append(args)
        return []

    def list_impl(self, query):
        self.list_paths.append(list(query.paths))
        return [self.rows[path] for path in query.paths if path in self.rows]

    def raw_create(self, tls, path, type_, props, user_properties, create_ancestors, encrypt):
        self.created.append((path, props))
        self.rows[path] = {"name": path, "type": type_, "properties": {}}

    def create(self, data):
        return resource_create.create_impl(self.context, Mock(), data)


def test_create_reports_headroom_and_user_property_name_together(monkeypatch):
    ancestor = row("tank", readonly="off", available=2 * GiB, usedbyrefreservation=GiB, special_small_blocks=0)
    stand = Stand([ancestor], monkeypatch)
    data = request(path="tank/vol", type="VOLUME", properties={"volsize": GiB}, user_properties={"nocolon": "x"})
    with pytest.raises(ValidationErrors) as exc_info:
        stand.create(data)
    assert sorted(e.attribute for e in exc_info.value.errors) == [
        f"{SCHEMA}.properties.refreservation",
        f"{SCHEMA}.user_properties",
    ]
    assert stand.created == []


def test_create_stops_at_a_volume_parent_before_later_rules_read_the_pool(monkeypatch):
    stand = Stand([row("tank/vol", "VOLUME", readonly="off"), row("tank", readonly="off")], monkeypatch)
    data = request(path="tank/vol/child", type="VOLUME", properties={"volsize": GiB}, user_properties={"nocolon": "x"})
    with pytest.raises(ValidationErrors) as exc_info:
        stand.create(data)
    assert errors_of(exc_info.value) == [(SCHEMA, "'tank/vol' is a volume and cannot hold 'tank/vol/child'.")]
    assert exc_info.value.errors[0].errno == errno.EINVAL
    assert stand.zpool_reads == []
    assert stand.created == []


def test_create_drops_a_zero_quota_and_keeps_a_zero_reservation(monkeypatch):
    stand = Stand([row("tank", readonly="off")], monkeypatch)
    entry = stand.create(request(path="tank/fs", properties={"quota": 0, "reservation": 0}))
    assert entry["name"] == "tank/fs"
    [(path, props)] = stand.created
    assert path == "tank/fs"
    assert "quota" not in props
    assert props["reservation"] == 0
