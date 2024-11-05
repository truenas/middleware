import contextlib

import pytest

from middlewared.service_exception import ValidationError
from middlewared.test.integration.utils import call, ssh

TEMP_BE_NAME = "temp_be_name"


@pytest.fixture(scope="module")
def orig_be():
    return call(
        "boot.environment.query",
        [["active", "=", True], ["activated", "=", True]],
        {"get": True},
    )


def be_query(be_name, get=True):
    return call("boot.environment.query", [["id", "=", be_name]], {"get": get})


@contextlib.contextmanager
def simulate_can_activate_is_false(be_ds):
    prop = "truenas:kernel_version"
    orig_value = ssh(f"zfs get {prop} {be_ds}").strip()
    assert orig_value
    try:
        temp = f"{prop}=-"
        ssh(f"zfs set {temp!r} {be_ds}")
        yield
    finally:
        orig = f"{prop}={orig_value}"
        ssh(f"zfs set {orig!r} {be_ds}")


def validate_activated_be(be_name, activate_string="R"):
    for line in ssh("zectl list -H").splitlines():
        values = line.split()
        be, activated = values[0], values[1]
        if be.strip() == be_name and activated.strip() == activate_string:
            break
    else:
        assert False, f"Failed to validate activated BE: {be_name!r}"


def get_zfs_property(ds_name, property):
    for line in ssh(f"zfs get {property} {ds_name} -H").splitlines():
        return line.split()


def test_failure_conditions_for_activate(orig_be):
    """
    1. test activating a non-existent BE fails
    2. test activating an already activated BE fails
    3. test destroying the active BE fails
    """
    with pytest.raises(ValidationError) as ve:
        call("boot.environment.activate", {"id": "CANARY"})
    assert ve.value.attribute == "boot.environment.activate"
    assert ve.value.errmsg == "'CANARY' not found"

    with pytest.raises(ValidationError) as ve:
        call("boot.environment.activate", {"id": orig_be["id"]})
    assert ve.value.attribute == "boot.environment.activate"
    assert ve.value.errmsg == f"{orig_be['id']!r} is already activated"

    with pytest.raises(ValidationError) as ve:
        call("boot.environment.destroy", {"id": orig_be["id"]})
    assert ve.value.attribute == "boot.environment.destroy"
    assert ve.value.errmsg == "Deleting the active boot environment is not allowed"


def test_clone_activate_keep_and_destroy(orig_be):
    """
    1. clone the active BE via api
    2. verify the cloned BE shows up in API
    3. verify the cloned BE exists on OS
    4. test activating non-functional BE fails
    5. activate the cloned BE via api
    6. verify the cloned BE shows activated in the API
    7. verify the cloned BE is activated on OS
    8. activate original BE
    9. verify the original BE is activated on OS
    10. mark a BE to be kept
    11. verify the BE is marked kept via the api
    12. verify the BE is marked kept on OS
    13. mark BE as to be NOT kept
    14. verify the BE is marked as not kept via the api
    15. verify the BE is marked not kept on OS
    16. destroy the cloned BE via api
    17. destroy the cloned BE is destroyed via the api
    18. verify the cloned BE is destroyed on OS
    """
    # step 1
    call("boot.environment.clone", {"id": orig_be["id"], "target": TEMP_BE_NAME})

    # step 2
    tmp = be_query(TEMP_BE_NAME)

    # step 3
    rv = ssh("zectl list -H").strip()
    assert TEMP_BE_NAME in rv, rv

    # step 4
    with simulate_can_activate_is_false(tmp["dataset"]):
        with pytest.raises(ValidationError) as ve:
            call("boot.environment.activate", {"id": tmp["id"]})
    assert ve.value.attribute == "boot.environment.activate"
    assert ve.value.errmsg == f"{tmp['id']!r} can not be activated"

    # step 5
    call("boot.environment.activate", {"id": TEMP_BE_NAME})

    # step 6
    rv = be_query(TEMP_BE_NAME)
    assert rv["activated"], rv

    # step 7
    validate_activated_be(TEMP_BE_NAME)

    # step 8
    call("boot.environment.activate", {"id": orig_be["id"]})
    rv = be_query(orig_be["id"])
    assert rv["activated"], rv

    # step 9
    validate_activated_be(orig_be["id"], activate_string="NR")

    # step 10
    call("boot.environment.keep", {"id": orig_be["id"], "value": True})

    # step 11
    rv = be_query(orig_be["id"])
    assert rv["keep"] is True, rv

    # step 12
    values = get_zfs_property(orig_be["dataset"], "zectl:keep")
    assert values[2] == "True"

    # step 13
    call("boot.environment.keep", {"id": orig_be["id"], "value": False})

    # step 14
    rv = be_query(orig_be["id"])
    assert rv["keep"] is False, rv

    # step 15
    values = get_zfs_property(orig_be["dataset"], "zectl:keep")
    assert values[2] == "False"

    # step 16
    call("boot.environment.destroy", {"id": TEMP_BE_NAME})

    # step 17
    rv = be_query(TEMP_BE_NAME, get=False)
    assert not rv, rv

    # step 18
    rv = ssh("zectl list -H").strip()
    assert TEMP_BE_NAME not in rv, rv


def test_promote_current_datasets():
    var_log = ssh("df | grep /var/log").split()[0]
    snapshot_name = "snap-1"
    snapshot = f"{var_log}@{snapshot_name}"
    ssh(f"zfs snapshot {snapshot}")
    try:
        clone = "boot-pool/ROOT/clone"
        ssh(f"zfs clone {snapshot} {clone}")
        try:
            ssh(f"zfs promote {clone}")
            assert (
                ssh(f"zfs get -H -o value origin {var_log}").strip()
                == f"{clone}@{snapshot_name}"
            )
            call("boot.environment.promote_current_datasets")
            assert ssh(f"zfs get -H -o value origin {var_log}").strip() == "-"
        finally:
            ssh(f"zfs destroy {clone}")
    finally:
        ssh(f"zfs destroy {snapshot}")
