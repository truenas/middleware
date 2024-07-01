#!/usr/bin/env python3
import argparse
import contextlib
import dataclasses
import functools
import json
import logging
import os
import subprocess
import sys
import textwrap

import libzfs
import pyudev

from middlewared.utils.filesystem import stat_x
from middlewared.utils.mount import getmntinfo


logger = logging.getLogger(__name__)


@dataclasses.dataclass
class ReadonlyState:
    original_root: bool = True
    original_usr: bool = True
    current_root: bool = True
    current_usr: bool = True


readonly_state = ReadonlyState()


@functools.cache
def get_ds_conf(root: str) -> dict[str, str]:
    conf_file = os.path.join(root, "conf/truenas_root_ds.json")
    try:
        with open(conf_file, "r") as f:
            conf = json.loads(f.read())
    except FileNotFoundError:
        raise ValueError(f"Unable to locate {conf_file!r}")

    usr_ds = next((i for i in conf if i["fhs_entry"]["name"] == "usr"))["ds"]
    return {
        "root": usr_ds.rsplit("/", 1)[0],
        "usr": usr_ds,
    }


def initialize_readonly_state(root: str):
    global readonly_state

    mountpoints = {
        root: "root",
        os.path.join(root, "usr"): "usr",
    }

    for mountpoint, key in mountpoints.items():
        try:
            st_mnt_id = stat_x.statx(mountpoint).stx_mnt_id
            readonly_val = 'RO' in getmntinfo(mnt_id=st_mnt_id)[st_mnt_id]['super_opts']
            for prefix in ("original_", "current_"):
                setattr(readonly_state, f"{prefix}{key}", readonly_val)
        except (FileNotFoundError, KeyError) as e:
            raise ValueError(f"Unable to determine readonly state for {mountpoint!r}: {e}")


def toggle_readonly(root, desired_value=None, restore_original_state=None):
    global readonly_state

    if desired_value is not None and restore_original_state is not None:
        raise ValueError("Both readonly_all_mountpoints and restore_state cannot be set at the same time")

    if desired_value is None and restore_original_state is None:
        raise ValueError("Either readonly_all_mountpoints or restore_state must be set")

    if restore_original_state is not None:
        mountpoints_mapping = {
            k.split("_")[-1]: v for k, v in readonly_state.__dict__.items() if k.startswith("original_")
        }
    else:
        mountpoints_mapping = {
            "root": desired_value,
            "usr": desired_value,
        }

    for key, value in filter(lambda i: i[0].startswith("current_"), readonly_state.__dict__.items()):
        key = key.split("_")[-1]
        if mountpoints_mapping[key] == value:
            mountpoints_mapping.pop(key)

    if not mountpoints_mapping:
        return

    # Some initramfs scripts use (`dpkg --print-architecture` or similar calls)
    if mountpoints_mapping.get("usr") is True:
        os.chmod(os.path.join(root, "usr/bin/dpkg"), 0o644)
        with contextlib.suppress(FileNotFoundError):
            # In the event this is called first with readonly set
            os.rename(os.path.join(root, "usr/local/bin/dpkg.bak"), os.path.join(root, "usr/local/bin/dpkg"))

    for device_key, ds_name in filter(lambda i: i[0] in mountpoints_mapping, get_ds_conf(root).items()):
        # Do not change `readonly` property when we're running in the installer, and it was not set yet
        if (
            subprocess.run(
                ["zfs", "get", "-H", "-o", "source", "readonly", ds_name],
                capture_output=True, text=True,
            ).stdout.strip() == "local"
        ):
            readonly_value = mountpoints_mapping[device_key]
            subprocess.run(["zfs", "set", f"readonly={'on' if readonly_value else 'off'}", ds_name])
            setattr(readonly_state, f"current_{device_key}", readonly_value)

    if mountpoints_mapping.get("usr") is False:
        os.chmod(os.path.join(root, "usr/bin/dpkg"), 0o755)
        with contextlib.suppress(FileNotFoundError):
            # In the event this is called twice with readonly unset
            # Basically `/usr/local/bin/dpkg` is a script we have written which explains that
            # package management is disabled on TrueNAS but when dev tools are installed,
            # we would like package management for the developer to work obviously
            os.rename(os.path.join(root, "usr/local/bin/dpkg"), os.path.join(root, "usr/local/bin/dpkg.bak"))


def update_zfs_default(root):
    with libzfs.ZFS() as zfs:
        existing_pools = [p.name for p in zfs.pools]

    for i in ['freenas-boot', 'boot-pool']:
        if i in existing_pools:
            boot_pool = i
            break
    else:
        raise CallError(f'Failed to locate valid boot pool. Pools located were: {", ".join(existing_pools)}')

    with libzfs.ZFS() as zfs:
        disks = [disk.replace("/dev/", "") for disk in zfs.get(boot_pool).disks]

    mapping = {}
    for dev in filter(
        lambda d: not d.sys_name.startswith("sr") and d.get("DEVTYPE") in ("disk", "partition"),
        pyudev.Context().list_devices(subsystem="block")
    ):
        if dev.get("DEVTYPE") == "disk":
            mapping[dev.sys_name] = dev.get("ID_BUS")
        elif dev.get("ID_PART_ENTRY_UUID"):
            parent = dev.find_parent("block")
            mapping[dev.sys_name] = parent.get("ID_BUS")
            mapping[os.path.join("disk/by-partuuid", dev.get("ID_PART_ENTRY_UUID"))] = parent.get("ID_BUS")

    has_usb = False
    for dev in disks:
        if mapping.get(dev) == "usb":
            has_usb = True
            break

    zfs_config_path = os.path.join(root, "etc/default/zfs")
    with open(zfs_config_path) as f:
        original_config = f.read()
        lines = original_config.rstrip().split("\n")

    zfs_var_name = "ZFS_INITRD_POST_MODPROBE_SLEEP"
    lines = [line for line in lines if not line.startswith(f"{zfs_var_name}=")]
    if has_usb:
        lines.append(f"{zfs_var_name}=15")

    new_config = "\n".join(lines) + "\n"
    if new_config != original_config:
        toggle_readonly(root, desired_value=False)
        with open(zfs_config_path, "w") as f:
            f.write(new_config)

        return True

    return False


def get_current_gpu_pci_ids(database):
    adv_config = query_config_table("system_advanced", database, "adv_")
    to_isolate = [gpu for gpu in get_gpus() if gpu["addr"]["pci_slot"] in adv_config.get("isolated_gpu_pci_ids", [])]
    return [dev["pci_slot"] for gpu in to_isolate for dev in gpu["devices"]]


def update_pci_module_files(root, config):
    # This method is (and must be) called when root is writeable

    def get_path(p):
        return os.path.join(root, p)

    pci_slots = config["pci_ids"]
    for path in map(
        get_path, [
            'etc/initramfs-tools/scripts/init-top/truenas_bind_vfio.sh',
            "etc/initramfs-tools/modules",
            "etc/modules",
            "etc/modprobe.d/kvm.conf",
            "etc/modprobe.d/nvidia.conf",
        ]
    ):
        with contextlib.suppress(Exception):
            os.unlink(path)

    os.makedirs(get_path("etc/initramfs-tools"), exist_ok=True)
    os.makedirs(get_path("etc/modprobe.d"), exist_ok=True)

    if not pci_slots:
        for path in map(
            get_path, [
                "etc/initramfs-tools/modules",
                "etc/modules",
            ]
        ):
            with open(path, "w"):
                pass

        return

    for path in map(get_path, ["etc/initramfs-tools/modules", "etc/modules"]):
        with open(path, "w") as f:
            f.write(textwrap.dedent("""\
                vfio
                vfio_iommu_type1
                vfio_virqfd
                vfio_pci
            """))

    with open(get_path("etc/modprobe.d/kvm.conf"), "w") as f:
        f.write("options kvm ignore_msrs=1\n")

    with open(get_path("etc/modprobe.d/nvidia.conf"), "w") as f:
        f.write(textwrap.dedent("""\
            softdep nouveau pre: vfio-pci
            softdep nvidia pre: vfio-pci
            softdep nvidia* pre: vfio-pci
        """))

    with open(get_path("etc/initramfs-tools/scripts/init-top/truenas_bind_vfio.sh"), "w") as f:
        f.write(textwrap.dedent(f"""\
            #!/bin/sh
            PREREQS=""
            DEVS="{' '.join(pci_slots)}"
            for DEV in $DEVS;
              do echo "vfio-pci" > /sys/bus/pci/devices/$DEV/driver_override
            done
            modprobe -i vfio-pci
        """))
    os.chmod(get_path("etc/initramfs-tools/scripts/init-top/truenas_bind_vfio.sh"), 0o755)


def update_pci_initramfs_config(root, database):
    initramfs_config_path = os.path.join(root, "boot/initramfs_config.json")
    initramfs_config = {
        "pci_ids": get_current_gpu_pci_ids(database),
    }
    original_config = None
    if os.path.exists(initramfs_config_path):
        with open(initramfs_config_path, "r") as f:
            original_config = json.loads(f.read())

    if initramfs_config != original_config:
        toggle_readonly(root, desired_value=False)

        with open(initramfs_config_path, "w") as f:
            f.write(json.dumps(initramfs_config))

        update_pci_module_files(root, initramfs_config)
        return True

    return False


def update_zfs_module_config(root, database):
    options = []
    for tunable in query_table("system_tunable", database, "tun_"):
        if tunable["type"] != "ZFS":
            continue
        if not tunable["enabled"]:
            continue

        options.append(f"{tunable['var']}={tunable['value']}")

    if options:
        config = f"options zfs {' '.join(options)}\n"
    else:
        config = None

    config_path = os.path.join(root, "etc", "modprobe.d", "zfs.conf")
    try:
        with open(config_path) as f:
            existing_config = f.read()
    except FileNotFoundError:
        existing_config = None

    if existing_config != config:
        toggle_readonly(root, desired_value=False)

        if config is None:
            os.unlink(config_path)
        else:
            with open(config_path, "w") as f:
                f.write(config)

        return True

    return False


if __name__ == "__main__":
    root = None
    try:
        p = argparse.ArgumentParser()
        p.add_argument("chroot", nargs=1)
        p.add_argument("--database", "-d", default="")
        p.add_argument("--force", "-f", action="store_true")
        args = p.parse_args()
        root = args.chroot[0]
        if root != "/":
            sys.path.insert(0, os.path.join(root, "usr/lib/python3/dist-packages"))

        initialize_readonly_state(root)

        from middlewared.service_exception import CallError
        from middlewared.utils.db import FREENAS_DATABASE, query_config_table, query_table
        from middlewared.utils.gpu import get_gpus

        database = args.database or os.path.join(root, FREENAS_DATABASE[1:])

        if update_required := any((
            args.force,
            update_zfs_default(root),
            update_pci_initramfs_config(root, database),
            update_zfs_module_config(root, database),
        )):
            toggle_readonly(root, desired_value=False)
            subprocess.run(["chroot", root, "update-initramfs", "-k", "all", "-u"], check=True)
    except Exception:
        logger.error("Failed to update initramfs", exc_info=True)
        exit(2)
    finally:
        if root is not None:
            toggle_readonly(root, restore_original_state=True)

    # We give out an exit code of 1 when initramfs has been updated as we require a reboot of the system for the
    # changes to have an effect. This caters to the case of uploading a database. Otherwise, we give an exit code
    # of 0 and in case of erring out
    exit(int(update_required))
