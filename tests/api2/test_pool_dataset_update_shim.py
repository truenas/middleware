import errno
import os
import time

import pytest
from auto_config import pool_name
from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, client, ssh


def read(path, properties):
    return call("zfs.resource.list", {"paths": [path], "properties": properties, "get_source": True})[0]["properties"]


def attributes(exc_info):
    return [error.attribute for error in exc_info.value.errors]


def test_compression_uppercase_value_round_trips():
    with dataset("shim_compression") as path:
        call("pool.dataset.update", path, {"compression": "LZ4"})
        assert read(path, ["compression"])["compression"]["raw"] == "lz4"


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


def test_empty_payload_emits_changed():
    with dataset("shim_empty_payload") as path:
        events = []

        def collect(mtype, **message):
            if mtype == "CHANGED" and message.get("id") == path:
                events.append(mtype)

        with client() as c:
            c.subscribe("pool.dataset.query", collect, sync=True)
            entry = call("pool.dataset.update", path, {})
            time.sleep(5)

        assert entry["id"] == path
        assert events == ["CHANGED"]
