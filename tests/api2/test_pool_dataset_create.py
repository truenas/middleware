from itertools import product
from re import escape

import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, pool


def test_create_dataset_nonexistent_pool():
    bad = "does_not_exist_zpool"
    with pytest.raises(
        ValidationErrors,
        match=escape(f"[EINVAL] pool_dataset_create.name: zpool ({bad}) does not exist.\n")
    ):
        with dataset("zz", pool=bad):
            pass


def test_create_dataset_nonexistent_parent_ds():
    bad = "zz"
    with pytest.raises(
        ValidationErrors,
        match=escape(f"[EINVAL] pool_dataset_create.name: Parent dataset ({pool}/{bad}) does not exist.\n")
    ):
        with dataset(f"{bad}/bleh"):
            pass


@pytest.mark.parametrize("child", ["a/b", "a/b/c"])
def test_pool_dataset_create_ancestors(child):
    with dataset("ancestors_create_test") as test_ds:
        name = f"{test_ds}/{child}"
        call("pool.dataset.create", {"name": name, "create_ancestors": True})
        call("pool.dataset.get_instance", name)


def test_pool_dataset_query():
    fields = ("id", "name")
    ops = ("=", "in")
    flats = (True, False)

    with dataset("query_test") as ds:
        # Try all combinations
        results = (call(
            "pool.dataset.query",
            [[field, op, ds if op == "=" else [ds]]],
            {"extra": {"flat": flat, "properties": []}}
        ) for field, op, flat in product(fields, ops, flats))

        # Check all the returns are the same
        first = next(results)
        for next_ds in results:
            assert next_ds == first


def _mount_opt_props(ds_name):
    return call(
        "zfs.resource.query",
        {"paths": [ds_name], "properties": ["exec", "devices", "setuid"]},
    )[0]["properties"]


def test_filesystem_default_mount_options_locked_off():
    with dataset("mount_opts_default") as ds:
        props = _mount_opt_props(ds)
        for p in ("exec", "devices", "setuid"):
            assert props[p]["value"] == "off", (p, props[p])
            assert props[p]["source"]["type"] == "LOCAL", (p, props[p])


def test_filesystem_exec_explicit_on_is_respected():
    with dataset("mount_opts_exec_on", {"exec": "ON"}) as ds:
        props = _mount_opt_props(ds)
        assert props["exec"]["value"] == "on"
        assert props["devices"]["value"] == "off"
        assert props["setuid"]["value"] == "off"


def test_volume_create_unaffected_by_filesystem_mount_opts():
    # exec/devices/setuid are filesystem-only ZFS properties; regression guard
    # that the injection doesn't fire for VOLUME type (ZFS would reject the create).
    with dataset("mount_opts_zvol", {"type": "VOLUME", "volsize": 1024 ** 3, "sparse": True}):
        pass


def test_apps_share_type_forces_exec_on():
    # APPS share_type hard-codes exec=ON (like SMB hard-codes acltype/aclmode),
    # overriding both the FILESYSTEM-default exec=off and any caller-provided
    # exec value.
    with dataset("mount_opts_apps", {"share_type": "APPS", "exec": "OFF"}) as ds:
        props = _mount_opt_props(ds)
        assert props["exec"]["value"] == "on"
        assert props["exec"]["source"]["type"] == "LOCAL"
        assert props["devices"]["value"] == "off"
        assert props["setuid"]["value"] == "off"
