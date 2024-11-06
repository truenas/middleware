# TrueNAS SCALE Websocket API tests
This folder stores Websocket (and a few REST) API tests.

## Dependencies required to run tests from a Debian based OS

`apt install python3-pip samba smbclient sshpass snmp libiscsi-dev`

In middleware/tests run the command bellow

`pip3 install -r requirements.txt`

## Running the API test(s)
runtests.py is the mechanism to kick off API runs. To see usage, call it without arguments.

### Example of command

`./runtests.py --ip 192.168.2.45 --interface em0 --password testing`

Below is a command to run a specific test:
`./runtests.py --ip 192.168.2.45 --interface em0 --password testing --test test_lock.py`

Below is a command to run specific tests:
`./runtests.py --ip 192.168.2.45 --interface em0 --password testing --test test_lock.py,test_mail.py`

## How should a Websocket API test be written?

### Code example
```
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
```

