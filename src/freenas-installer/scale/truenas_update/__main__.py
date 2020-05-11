# -*- coding=utf-8 -*-
import glob
import json
import logging
import subprocess
import sys

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    update = json.loads(sys.stdin.read())

    root = update["root"]

    subprocess.run(
        [
            "rsync", "-aRx",
            "--exclude", "/data/factory-v1.db",
            "--exclude", "/data/manifest.json",
            "/etc/default/grub.d/truenas.cfg", "/etc/hostid", "/data", "/root",
            f"{root}/",
        ],
        check=True,
    )

    undo = []
    try:
        subprocess.run(["mount", "-t", "proc", "none", f"{root}/proc"], check=True)
        undo.append(["umount", f"{root}/proc"])

        subprocess.run(["mount", "-t", "sysfs", "none", f"{root}/sys"], check=True)
        undo.append(["umount", f"{root}/sys"])

        for device in glob.glob("/dev/sd?*") + ["/dev/zfs"]:
            subprocess.run(["touch", f"{root}{device}"], check=True)
            subprocess.run(["mount", "-o", "bind", device, f"{root}{device}"], check=True)
            undo.append(["umount", f"{root}{device}"])

        subprocess.run(["chroot", root, "update-initramfs", "-k", "all", "-u"], check=True)
        subprocess.run(["chroot", root, "update-grub"], check=True)

        subprocess.run(["zpool", "set", f"bootfs={update['dataset_name']}", update["pool_name"]])
        for disk in update["disks"]:
            subprocess.run(["chroot", root, "grub-install", f"/dev/{disk}"], check=True)
    finally:
        for cmd in reversed(undo):
            subprocess.run(cmd, check=True)
