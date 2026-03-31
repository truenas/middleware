import contextlib
import textwrap

import pytest

from auto_config import ha
from truenas_api_client import ValidationErrors
from middlewared.test.integration.utils import call, ssh, truenas_server
from middlewared.test.integration.utils.mock_binary import mock_binary

SYSCTL = "kernel.watchdog"
SYSCTL_DEFAULT_VALUE = "1"
SYSCTL_NEW_VALUE = "0"

ZFS = "zil_nocacheflush"
ZFS_DEFAULT_VALUE = "0"
ZFS_NEW_VALUE = "1"


def assert_ssh_both_nodes(command, output, **kwargs):
    ips = [None]
    if ha:
        ips.append(truenas_server.ha_ips()["standby"])

        assert ssh(command, **kwargs) == output


def test_create_invalid_sysctl():
    with pytest.raises(ValidationErrors) as ve:
        call("tunable.create", {
            "type": "SYSCTL",
            "var": "kernel.truenas",
            "value": "1",
        }, job=True)

    assert ve.value.errors[0].attribute == "tunable_create.var"


def test_create_invalid_udev():
    with pytest.raises(ValidationErrors) as ve:
        call("tunable.create", {
            "type": "UDEV",
            "var": "61-truenas-pmem",
            "value": "# disable built-in truenas rule to enable memory loss",
        }, job=True)

    assert ve.value.errors[0].attribute == "tunable_create.var"


def test_create_invalid_zfs():
    with pytest.raises(ValidationErrors) as ve:
        call("tunable.create", {
            "type": "ZFS",
            "var": "zfs_truenas",
            "value": "1",
        }, job=True)

    assert ve.value.errors[0].attribute == "tunable_create.var"


def test_sysctl_lifecycle():
    def assert_default_value():
        assert_ssh_both_nodes("cat /etc/sysctl.d/tunables.conf", "", check=False)
        assert_ssh_both_nodes(f"sysctl -n {SYSCTL}", f"{SYSCTL_DEFAULT_VALUE}\n")

    def assert_new_value():
        assert_ssh_both_nodes("cat /etc/sysctl.d/tunables.conf", f"{SYSCTL}={SYSCTL_NEW_VALUE}\n")
        assert_ssh_both_nodes(f"sysctl -n {SYSCTL}", f"{SYSCTL_NEW_VALUE}\n")

    assert_default_value()

    tunable = call("tunable.create", {
        "type": "SYSCTL",
        "var": SYSCTL,
        "value": SYSCTL_NEW_VALUE,
    }, job=True)

    assert_new_value()

    call("tunable.update", tunable["id"], {
        "enabled": False,
    }, job=True)

    assert_default_value()

    call("tunable.update", tunable["id"], {
        "enabled": True,
    }, job=True)

    assert_new_value()

    call("tunable.delete", tunable["id"], job=True)

    assert_default_value()


def test_udev_lifecycle():
    def assert_exists():
        assert_ssh_both_nodes(
            "cat /etc/udev/rules.d/10-disable-usb.rules",
            f"BUS==\"usb\", OPTIONS+=\"ignore_device\"\n",
        )

    def assert_does_not_exist():
        assert_ssh_both_nodes("cat /etc/udev/rules.d/10-disable-usb.rules", "", check=False)

    tunable = call("tunable.create", {
        "type": "UDEV",
        "var": "10-disable-usb",
        "value": "BUS==\"usb\", OPTIONS+=\"ignore_device\""
    }, job=True)

    assert_exists()

    call("tunable.update", tunable["id"], {
        "enabled": False,
    }, job=True)

    assert_does_not_exist()

    call("tunable.update", tunable["id"], {
        "enabled": True,
    }, job=True)

    assert_exists()

    call("tunable.delete", tunable["id"], job=True)

    assert_does_not_exist()


def test_zfs_lifecycle():
    binary = "/usr/sbin/update-initramfs"
    code = textwrap.dedent("""\
        import os

        path = "/tmp/mock-update-initramfs-run-count"
        if os.path.exists(path):
            run_count = int(open(path).read().strip())
        else:
            run_count = 0
        
        run_count += 1
        
        with open(path, "w") as f:
            f.write(f"{run_count}\\n")
    """)
    exitcode = 0

    with contextlib.ExitStack() as stack:
        stack.enter_context(mock_binary(binary, code=code, exitcode=exitcode))
        if ha:
            stack.enter_context(
                mock_binary(binary, code=code, exitcode=exitcode, remote=True)
            )

        def assert_default_value():
            assert_ssh_both_nodes("cat /etc/modprobe.d/zfs.conf", "", check=False)
            assert_ssh_both_nodes(f"cat /sys/module/zfs/parameters/{ZFS}", f"{ZFS_DEFAULT_VALUE}\n")

        def assert_new_value():
            assert_ssh_both_nodes("cat /etc/modprobe.d/zfs.conf", f"options zfs {ZFS}={ZFS_NEW_VALUE}\n", check=False)
            assert_ssh_both_nodes(f"cat /sys/module/zfs/parameters/{ZFS}", f"{ZFS_NEW_VALUE}\n")

        def assert_update_initramfs_run_count(value):
            assert_ssh_both_nodes(f"cat /tmp/mock-update-initramfs-run-count", f"{value}\n")

        assert_default_value()

        tunable = call("tunable.create", {
            "type": "ZFS",
            "var": ZFS,
            "value": ZFS_NEW_VALUE,
        }, job=True)

        assert_new_value()
        assert_update_initramfs_run_count(1)

        call("tunable.update", tunable["id"], {
            "enabled": False,
        }, job=True)

        assert_default_value()
        assert_update_initramfs_run_count(2)

        call("tunable.update", tunable["id"], {
            "enabled": True,
        }, job=True)

        assert_new_value()
        assert_update_initramfs_run_count(3)

        call("tunable.delete", tunable["id"], job=True)

        assert_default_value()
        assert_update_initramfs_run_count(4)


def test_arc_max_set():
    tunable = call("tunable.create", {"type": "ZFS", "var": "zfs_arc_max", "value": "8675309"}, job=True)
    try:
        val = ssh("cat /sys/module/zfs/parameters/zfs_arc_max")
    finally:
        call("tunable.delete", tunable["id"], job=True)

    assert int(val.strip()) == 8675309

    mount_info = call("filesystem.mount_info", [["mountpoint", "=", "/"]], {"get": True})
    assert "RO" in mount_info["mount_opts"]


def test_create_error():
    assert call("tunable.query") == []

    with pytest.raises(Exception) as ve:
        call("tunable.create", {
            "type": "SYSCTL",
            "var": "kernel.watchdog",
            "value": "6",
        }, job=True)

    assert "Invalid argument" in str(ve.value)

    assert call("tunable.query") == []


def test_update_error():
    assert call("tunable.query") == []

    tunable = call("tunable.create", {
        "type": "SYSCTL",
        "var": "kernel.watchdog",
        "value": "0",
    }, job=True)

    try:
        with pytest.raises(Exception) as ve:
            call("tunable.update", tunable["id"], {
                "value": "6",
            }, job=True)

        assert "Invalid argument" in str(ve.value)

        assert call("tunable.get_instance", tunable["id"])["value"] == "0"
    finally:
        call("tunable.delete", tunable["id"], job=True)
