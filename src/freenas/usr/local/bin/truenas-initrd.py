#!/usr/bin/env python3
import contextlib
import json
import logging
import os
import subprocess
import sys
import textwrap

import libzfs
import pyudev


logger = logging.getLogger(__name__)


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
        with open(zfs_config_path, "w") as f:
            f.write(new_config)
        return True
    return False


def get_current_gpu_pci_ids(root):
    adv_config = query_config_table("system_advanced", os.path.join(root, FREENAS_DATABASE[1:]), "adv_")
    to_isolate = [gpu for gpu in get_gpus() if gpu["addr"]["pci_slot"] in adv_config.get("isolated_gpu_pci_ids", [])]
    return [dev["pci_id"] for gpu in to_isolate for dev in gpu["devices"]]


def update_module_files(root, config):
    def get_path(p):
        return os.path.join(root, p)

    pci_ids = config["pci_ids"]
    for path in map(
        get_path, [
            "etc/initramfs-tools/modules",
            "etc/modules",
            "etc/modprobe.d/kvm.conf",
            "etc/modprobe.d/nvidia.conf",
            "etc/modprobe.d/vfio.conf",
        ]
    ):
        with contextlib.suppress(Exception):
            os.unlink(path)
    if not pci_ids:
        return

    os.makedirs(get_path("etc/initramfs-tools"), exist_ok=True)
    os.makedirs(get_path("etc/modprobe.d"), exist_ok=True)

    for path in map(get_path, ["etc/initramfs-tools/modules", "etc/modules"]):
        with open(path, "w") as f:
            f.write(textwrap.dedent(f"""\
                vfio
                vfio_iommu_type1
                vfio_virqfd
                vfio_pci ids={','.join(pci_ids)}
            """))

    with open(get_path("etc/modprobe.d/kvm.conf"), "w") as f:
        f.write("options kvm ignore_msrs=1\n")

    with open(get_path("etc/modprobe.d/nvidia.conf"), "w") as f:
        f.write(textwrap.dedent("""\
            softdep nouveau pre: vfio-pci
            softdep nvidia pre: vfio-pci
            softdep nvidia* pre: vfio-pci
        """))

    with open(get_path("etc/modprobe.d/vfio.conf"), "w") as f:
        f.write(f"options vfio-pci ids={','.join(pci_ids)}\n")


def update_initramfs_config(root):
    initramfs_config_path = os.path.join(root, "boot/initramfs_config.json")
    initramfs_config = {
        "pci_ids": get_current_gpu_pci_ids(root),
    }
    original_config = None
    if os.path.exists(initramfs_config_path):
        with open(initramfs_config_path, "r") as f:
            original_config = json.loads(f.read())

    if initramfs_config != original_config:
        with open(initramfs_config_path, "w") as f:
            f.write(json.dumps(initramfs_config))

        update_module_files(root, initramfs_config)
        return True

    return False


if __name__ == "__main__":
    try:
        root = sys.argv[1]
        if root != "/":
            sys.path.insert(0, os.path.join(root, "usr/lib/python3/dist-packages"))

        from middlewared.service_exception import CallError
        from middlewared.utils.db import FREENAS_DATABASE, query_config_table
        from middlewared.utils.gpu import get_gpus

        update_required = update_zfs_default(root) | update_initramfs_config(root)
        if update_required:
            subprocess.run(["chroot", root, "update-initramfs", "-k", "all", "-u"], check=True)
    except Exception:
        logger.error("Failed to update initramfs", exc_info=True)
        exit(2)

    # We give out an exit code of 1 when initramfs has been updated as we require a reboot of the system for the
    # changes to have an effect. This caters to the case of uploading a database. Otherwise we give an exit code
    # of 0 and in case of erring out
    exit(int(update_required))
