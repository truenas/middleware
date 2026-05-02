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

ZFS_MODPROBE_PATH = "/data/subsystems/initramfs/truenas_zfs_modprobe.conf"

UPDATE_INITRAMFS_BINARY = "/usr/sbin/update-initramfs"
UPDATE_INITRAMFS_RUN_COUNT_PATH = "/tmp/mock-update-initramfs-run-count"
UPDATE_INITRAMFS_MOCK_CODE = textwrap.dedent("""\
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


def assert_ssh_both_nodes(command, output, **kwargs):
    ips = [None]
    if ha:
        ips.append(truenas_server.ha_ips()["standby"])

    for ip in ips:
        assert ssh(command, ip=ip, **kwargs) == output


@contextlib.contextmanager
def mock_update_initramfs():
    """
    Replace `update-initramfs` with a counter-incrementing Python mock on
    both nodes for the duration of the block, and reset the counter on
    entry so callers can assert absolute values via
    `assert_update_initramfs_run_count`.
    """
    with contextlib.ExitStack() as stack:
        stack.enter_context(mock_binary(
            UPDATE_INITRAMFS_BINARY, code=UPDATE_INITRAMFS_MOCK_CODE, exitcode=0,
        ))
        if ha:
            stack.enter_context(mock_binary(
                UPDATE_INITRAMFS_BINARY, code=UPDATE_INITRAMFS_MOCK_CODE,
                exitcode=0, remote=True,
            ))
        assert_ssh_both_nodes(
            f"rm -f {UPDATE_INITRAMFS_RUN_COUNT_PATH} && echo ok", "ok\n",
        )
        yield


def assert_update_initramfs_run_count(value):
    # `|| echo 0` so the assertion works before the mock has been invoked
    # (i.e., the counter file doesn't exist yet).
    assert_ssh_both_nodes(
        f"cat {UPDATE_INITRAMFS_RUN_COUNT_PATH} 2>/dev/null || echo 0",
        f"{value}\n",
    )


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
            "BUS==\"usb\", OPTIONS+=\"ignore_device\"\n",
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
    with mock_update_initramfs():
        def assert_default_value():
            assert_ssh_both_nodes(f"cat {ZFS_MODPROBE_PATH}", "", check=False)
            assert_ssh_both_nodes(f"cat /sys/module/zfs/parameters/{ZFS}", f"{ZFS_DEFAULT_VALUE}\n")

        def assert_new_value():
            assert_ssh_both_nodes(f"cat {ZFS_MODPROBE_PATH}", f"options zfs {ZFS}={ZFS_NEW_VALUE}\n", check=False)
            assert_ssh_both_nodes(f"cat /sys/module/zfs/parameters/{ZFS}", f"{ZFS_NEW_VALUE}\n")

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


def test_zfs_no_rebuild_when_modprobe_unchanged():
    """
    Cover update_initramfs's change-detection optimization: when a ZFS
    tunable mutation does not change the materialized modprobe file
    content, update-initramfs must NOT be invoked. Only enabled tunables
    contribute to the file, so updating the value of a *disabled* tunable
    leaves the file unchanged and must not trigger an initramfs rebuild.

    Without this test, a regression that always passed force=True (or that
    skipped the write_zfs_modprobe content comparison) would silently
    rebuild the initrd on every tunable update.
    """
    # Distinct values are required for the test to actually exercise
    # do_update's full path (otherwise it short-circuits on entry-equality).
    assert ZFS_NEW_VALUE != ZFS_DEFAULT_VALUE

    with mock_update_initramfs():
        # Disabled ZFS tunable: do_create's ZFS branch is gated on `enabled`,
        # so update_initramfs is not called and the modprobe file is untouched.
        tunable = call("tunable.create", {
            "type": "ZFS",
            "var": ZFS,
            "value": ZFS_NEW_VALUE,
            "enabled": False,
        }, job=True)
        try:
            assert_ssh_both_nodes(f"cat {ZFS_MODPROBE_PATH}", "", check=False)
            assert_update_initramfs_run_count(0)

            # Real value change. do_update's old != new short-circuit at
            # crud.py:121 does NOT fire, so update_initramfs is invoked.
            # write_zfs_modprobe queries enabled ZFS tunables, finds none,
            # produces empty content matching the already-empty (missing)
            # modprobe file, and returns False — so boot.update_initramfs
            # runs with force=False and the existing initrd is kept.
            call("tunable.update", tunable["id"], {
                "value": ZFS_DEFAULT_VALUE,
            }, job=True)

            # Confirm do_update actually ran the update (proves we are not
            # accidentally hitting the entry-equality short-circuit).
            assert call("tunable.get_instance", tunable["id"])["value"] == ZFS_DEFAULT_VALUE

            assert_ssh_both_nodes(f"cat {ZFS_MODPROBE_PATH}", "", check=False)
            assert_update_initramfs_run_count(0)
        finally:
            call("tunable.delete", tunable["id"], job=True)


def test_zfs_no_rebuild_on_metadata_only_change():
    """
    do_update must not invoke `update-initramfs` (or rewrite the live ZFS
    parameter) when a ZFS tunable's `value`/`enabled` haven't changed.
    Editing a cosmetic field like `comment` doesn't affect kernel state or
    the modprobe file, so the kernel write and initramfs rebuild are
    skipped entirely.
    """
    with mock_update_initramfs():
        tunable = call("tunable.create", {
            "type": "ZFS",
            "var": ZFS,
            "value": ZFS_NEW_VALUE,
        }, job=True)
        try:
            # Create on enabled tunable bumps the counter once.
            assert_update_initramfs_run_count(1)

            call("tunable.update", tunable["id"], {
                "comment": "metadata-only change",
            }, job=True)

            # The update persisted in the DB...
            assert call("tunable.get_instance", tunable["id"])["comment"] == "metadata-only change"
            # ...but do_update skipped the kernel write and initramfs path.
            assert_update_initramfs_run_count(1)
        finally:
            call("tunable.delete", tunable["id"], job=True)


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
