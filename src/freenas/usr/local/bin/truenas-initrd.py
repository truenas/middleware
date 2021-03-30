#!/usr/bin/env python3
import json
import os
import subprocess
import sys

import libzfs
import pyudev
import sqlite3


def update_zfs_default():
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
        with open(zfs_config_path, "w") as f:
            f.write(new_config)
        return True
    return False


def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


def get_current_gpu_pci_ids():
    from middlewared.plugins.config import FREENAS_DATABASE
    from middlewared.utils.gpu import get_gpus
    conn = sqlite3.connect(FREENAS_DATABASE)
    conn.row_factory = dict_factory
    c = conn.cursor()
    c.execute("SELECT * FROM system_advanced")
    adv_config = {k.replace("adv_", ""): v for k, v in c.fetchone().items()}
    to_isolate = [gpu for gpu in get_gpus() if gpu["addr"]["pci_slot"] in adv_config["isolated_gpu_pci_ids"]]
    return [dev["pci_id"] for gpu in to_isolate for dev in gpu["devices"]]


def update_initramfs_config():
    initramfs_config_path = "/boot/initramfs_config.json"
    initramfs_config = {
        "pci_ids": get_current_gpu_pci_ids(),
    }
    original_config = None
    if os.path.exists(initramfs_config_path):
        with open(initramfs_config_path, "r") as f:
            original_config = json.loads(f.read())

    if initramfs_config != original_config:
        with open(initramfs_config_path, "w") as f:
            f.write(json.dumps(initramfs_config))
        return True

    return False


if __name__ == "__main__":
    boot_pool, root, update_initramfs_if_changes = sys.argv[1:]
    if root != "/":
        sys.path.append(os.path.join(root, "usr/lib/python3/dist-packages/middlewared"))

    update_required = update_zfs_default() and update_initramfs_config()
    if update_required and update_initramfs_if_changes == "1":
        subprocess.run(["chroot", root, "update-initramfs", "-k", "all", "-u"], check=True)
