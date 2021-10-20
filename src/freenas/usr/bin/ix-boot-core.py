#!/usr/bin/python3
import subprocess
import sys


if __name__ == "__main__":
    boot_pool = "boot-pool"
    if subprocess.run(["zfs", "list", "boot-pool"], capture_output=True).returncode != 0:
        boot_pool = "freenas-boot"

    for line in subprocess.run(
        ["zfs", "list", "-H", "-o", "name,truenas:12", "-r", f"{boot_pool}/ROOT"],
        capture_output=True, text=True, check=True,
    ).stdout.splitlines():
        name, truenas_12 = line.split("\t")
        if truenas_12 == "1":
            break
    else:
        sys.stderr.write(f"No dataset with truenas:12=1 found on {boot_pool}\n")
        sys.exit(1)

    subprocess.run(["zpool", "set", f"bootfs={name}", boot_pool], check=True)
    subprocess.run(["update-grub"], check=True)
    subprocess.run(["reboot"], check=True)
