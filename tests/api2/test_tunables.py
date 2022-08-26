import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.utils import call, ssh

SYSCTL = "kernel.watchdog"
SYSCTL_DEFAULT_VALUE = "1"
SYSCTL_NEW_VALUE = "0"


def test_create_invalid_sysctl():
    with pytest.raises(ValidationErrors) as ve:
        call("tunable.create", {
            "type": "SYSCTL",
            "var": "kernel.truenas",
            "value": "1",
        })

    assert ve.value.errors[0].attribute == "tunable_create.var"


def test_create_invalid_udev():
    with pytest.raises(ValidationErrors) as ve:
        call("tunable.create", {
            "type": "UDEV",
            "var": "61-truenas-pmem",
            "value": "# disable built-in truenas rule to enable memory loss",
        })

    assert ve.value.errors[0].attribute == "tunable_create.var"


def test_sysctl_lifecycle():
    def assert_default_value():
        assert ssh("cat /etc/sysctl.d/tunables.conf", check=False) == f""
        assert ssh(f"sysctl -n {SYSCTL}") == f"{SYSCTL_DEFAULT_VALUE}\n"

    def assert_new_value():
        assert ssh("cat /etc/sysctl.d/tunables.conf") == f"{SYSCTL}={SYSCTL_NEW_VALUE}\n"
        assert ssh(f"sysctl -n {SYSCTL}") == f"{SYSCTL_NEW_VALUE}\n"

    assert_default_value()

    tunable = call("tunable.create", {
        "type": "SYSCTL",
        "var": SYSCTL,
        "value": SYSCTL_NEW_VALUE,
    })

    assert_new_value()

    call("tunable.update", tunable["id"], {
        "enabled": False,
    })

    assert_default_value()

    call("tunable.update", tunable["id"], {
        "enabled": True,
    })

    assert_new_value()

    call("tunable.delete", tunable["id"])

    assert_default_value()


def test_udev_lifecycle():
    def assert_exists():
        assert ssh("cat /etc/udev/rules.d/10-disable-usb.rules") == f"BUS==\"usb\", OPTIONS+=\"ignore_device\"\n"

    def assert_does_not_exist():
        assert ssh("cat /etc/udev/rules.d/10-disable-usb.rules", check=False) == f""

    tunable = call("tunable.create", {
        "type": "UDEV",
        "var": "10-disable-usb",
        "value": "BUS==\"usb\", OPTIONS+=\"ignore_device\""
    })

    assert_exists()

    call("tunable.update", tunable["id"], {
        "enabled": False,
    })

    assert_does_not_exist()

    call("tunable.update", tunable["id"], {
        "enabled": True,
    })

    assert_exists()

    call("tunable.delete", tunable["id"])

    assert_does_not_exist()
