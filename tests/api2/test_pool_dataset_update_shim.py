import contextlib
import errno
import os

import pytest
from auto_config import pool_name
from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.entitlements import entitled
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, ssh

GiB = 1024**3
MiB = 1024**2


def read(path, properties):
    return call("zfs.resource.list", {"paths": [path], "properties": properties, "get_source": True})[0]["properties"]


def attributes(exc_info):
    return [error.attribute for error in exc_info.value.errors]


@contextlib.contextmanager
def volume(name, volsize=GiB):
    with dataset(name, {"type": "VOLUME", "volsize": volsize}) as path:
        yield path


def test_dedup_uppercase_value_is_lowercased_for_zfs():
    with dataset("shim_dedup") as path:
        with entitled("DEDUP", True):
            call("pool.dataset.update", path, {"deduplication": "ON"})
        assert read(path, ["dedup"])["dedup"]["raw"] == "on"


def test_compression_uppercase_value_round_trips():
    with dataset("shim_compression") as path:
        call("pool.dataset.update", path, {"compression": "LZ4"})
        assert read(path, ["compression"])["compression"]["raw"] == "lz4"


def test_copies_is_passed_as_an_integer():
    with dataset("shim_copies") as path:
        call("pool.dataset.update", path, {"copies": 2})
        assert read(path, ["copies"])["copies"]["value"] == 2


def test_quota_zero_clears_a_quota():
    with dataset("shim_quota") as path:
        call("pool.dataset.update", path, {"quota": 2 * GiB})
        assert read(path, ["quota"])["quota"]["value"] == 2 * GiB

        call("pool.dataset.update", path, {"quota": 0})
        assert read(path, ["quota"])["quota"]["value"] == 0


def test_force_size_does_not_bypass_the_headroom_rule():
    with volume("shim_force_size") as path:
        props = read(path, ["available", "usedbyrefreservation"])
        base = props["available"]["value"] - props["usedbyrefreservation"]["value"]
        volsize = GiB + (base // MiB + 1) * MiB
        with pytest.raises(ValidationErrors) as exc_info:
            call("pool.dataset.update", path, {"volsize": volsize, "force_size": True})
        assert attributes(exc_info) == ["pool_dataset_update.volsize"]
        assert read(path, ["volsize"])["volsize"]["value"] == GiB


def test_two_zfs_side_errors_arrive_together():
    with dataset("shim_two_errors") as path:
        with pytest.raises(ValidationErrors) as exc_info:
            call("pool.dataset.update", path, {"recordsize": "3000", "special_small_block_size": 32 * MiB})
        assert sorted(attributes(exc_info)) == [
            "pool_dataset_update.recordsize",
            "pool_dataset_update.special_small_block_size",
        ]


def test_shim_error_and_zfs_side_error_arrive_together():
    with dataset("shim_mixed_errors") as path:
        with pytest.raises(ValidationErrors) as exc_info:
            call(
                "pool.dataset.update",
                path,
                {
                    "user_properties": [{"key": "custom:a", "value": "1"}],
                    "user_properties_update": [{"key": "custom:b", "value": "2"}],
                    "recordsize": "3000",
                },
            )
        assert attributes(exc_info) == [
            "pool_dataset_update.user_properties_update",
            "pool_dataset_update.recordsize",
        ]
        assert read(path, ["recordsize"])["recordsize"]["source"]["type"] != "LOCAL"


def test_value_the_zfs_model_rejects_is_a_validation_error():
    with dataset("shim_negative_ssb") as path:
        with pytest.raises(ValidationErrors) as exc_info:
            call("pool.dataset.update", path, {"special_small_block_size": -1})
        assert attributes(exc_info) == ["pool_dataset_update.special_small_block_size"]


def test_unentitled_dedup_is_keyed_on_deduplication():
    with dataset("shim_dedup_unentitled") as path:
        with entitled("DEDUP", False):
            with pytest.raises(ValidationErrors) as exc_info:
                call("pool.dataset.update", path, {"deduplication": "ON"})
        assert attributes(exc_info) == ["pool_dataset_update.deduplication"]


def test_zfs_side_user_property_error_is_keyed_on_user_properties_update():
    with dataset("shim_multiline_user_property") as path:
        with pytest.raises(ValidationErrors) as exc_info:
            call("pool.dataset.update", path, {"user_properties_update": [{"key": "custom:x", "value": "a\nb"}]})
        assert attributes(exc_info) == ["pool_dataset_update.user_properties_update"]


def test_received_companion_of_inherited_acltype_is_keyed_on_acltype():
    source = os.path.join(pool_name, "shim_received_src")
    target = os.path.join(pool_name, "shim_received_dst")
    acl = {"acltype": "posix", "aclmode": "discard", "aclinherit": "discard"}
    call("zfs.resource.create", {"path": source, "properties": acl})
    try:
        ssh(f"zfs snapshot {source}@snap")
        ssh(f"zfs send -p {source}@snap | zfs recv {target}")
        try:
            ssh(f"zfs set acltype=posix aclinherit=discard {target}")
            sources = read(target, ["acltype", "aclmode", "aclinherit"])
            assert {name: sources[name]["source"]["type"] for name in sources} == {
                "acltype": "LOCAL",
                "aclmode": "RECEIVED",
                "aclinherit": "LOCAL",
            }

            with pytest.raises(ValidationErrors) as exc_info:
                call("pool.dataset.update", target, {"acltype": "INHERIT"})
            assert attributes(exc_info) == ["pool_dataset_update.acltype"]
        finally:
            ssh(f"zfs destroy -r {target}")
    finally:
        call("zfs.resource.destroy", {"path": source, "recursive": True})


def test_internal_dataset_is_not_found():
    parent = os.path.join(pool_name, "shim_internal")
    internal = os.path.join(parent, "ix-apps")
    ssh(f"zfs create -p -o compression=zstd {internal}")
    try:
        with pytest.raises(ValidationErrors) as exc_info:
            call("pool.dataset.update", internal, {"compression": "LZ4"})
        assert [(e.attribute, e.errno) for e in exc_info.value.errors] == [("id", errno.ENOENT)]
        assert read(internal, ["compression"])["compression"]["raw"] == "zstd"
    finally:
        ssh(f"zfs destroy -r {parent}")
