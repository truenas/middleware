from auto_config import pool_name
from middlewared.service_exception import ValidationError
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, ssh
import pytest

_256MiB = 268435456
_512MiB = 536870912
BASE_NAME = "test_resize_zvol"
BASE_ARGS = {"type": "VOLUME", "volsize": _256MiB, "volblocksize": "64K"}


def query_zvol(zvol):
    result = call(
        "zfs.resource.query",
        {"paths": [zvol], "properties": ["refreservation", "volsize"]},
    )
    assert result and len(result) == 1
    return (
        result[0]["properties"]["refreservation"]["value"],
        result[0]["properties"]["volsize"]["value"],
    )


def thick_refreservation(zvol):
    # the refreservation `zfs create -V` gives a volume of the same
    # size and block size (volsize plus metadata and raidz overhead)
    ref = f"{zvol}_ref"
    volsize, volblocksize = ssh(f"zfs get -Hpo value volsize,volblocksize {zvol}").split()
    ssh(f"zfs create -V {volsize} -o volblocksize={volblocksize} {ref}")
    try:
        return int(ssh(f"zfs get -Hpo value refreservation {ref}"))
    finally:
        ssh(f"zfs destroy {ref}")


def pool_available():
    result = call("zfs.resource.query", {"paths": [pool_name], "properties": ["available"]})
    return result[0]["properties"]["available"]["value"]


def grow_zvol(zvol, **kwargs):
    call("pool.dataset.update", zvol, {"volsize": _512MiB, "force_size": True, **kwargs})


def test_grow_thick_zvol_stays_thick():
    with dataset(f"{BASE_NAME}_thick", BASE_ARGS) as ds:
        grow_zvol(ds)
        rr, vs = query_zvol(ds)
        assert vs == _512MiB
        assert rr == thick_refreservation(ds)


def test_grow_sparse_zvol_stays_sparse():
    with dataset(f"{BASE_NAME}_sparse", BASE_ARGS | {"sparse": True}) as ds:
        grow_zvol(ds)
        assert query_zvol(ds) == (0, _512MiB)


def test_grow_zvol_keeps_partial_refreservation():
    with dataset(f"{BASE_NAME}_partial", BASE_ARGS | {"refreservation": _256MiB // 2}) as ds:
        grow_zvol(ds)
        assert query_zvol(ds) == (_256MiB // 2, _512MiB)


def test_grow_zvol_with_explicit_refreservation():
    with dataset(f"{BASE_NAME}_explicit", BASE_ARGS) as ds:
        grow_zvol(ds, refreservation=_256MiB)
        assert query_zvol(ds) == (_256MiB, _512MiB)


def test_grow_readonly_zvol_keeps_refreservation():
    # ZFS sets each property on its own, so a resize that fails must not
    # leave a reservation for the new size behind
    with dataset(f"{BASE_NAME}_readonly", BASE_ARGS | {"readonly": "ON"}) as ds:
        before = query_zvol(ds)
        with pytest.raises(ValidationError, match="Failed to update properties"):
            grow_zvol(ds)
        assert query_zvol(ds) == before


def test_grow_locked_zvol_keeps_refreservation():
    encryption = {"encryption": True, "inherit_encryption": False, "encryption_options": {"passphrase": "testtest"}}
    with dataset(f"{BASE_NAME}_locked", BASE_ARGS | encryption) as ds:
        call("pool.dataset.lock", ds, job=True)
        before = query_zvol(ds)
        with pytest.raises(ValidationError, match="Failed to update properties"):
            grow_zvol(ds)
        assert query_zvol(ds) == before


def test_grow_thick_zvol_beyond_available_space():
    # the volume must not grow when the pool can't back its reservation
    with dataset(f"{BASE_NAME}_nospace", BASE_ARGS) as ds:
        before = query_zvol(ds)
        too_big = pool_available() // 65536 * 65536 * 2
        with pytest.raises(ValidationError, match="Failed to update properties"):
            call("pool.dataset.update", ds, {"volsize": too_big, "force_size": True})
        assert query_zvol(ds) == before
