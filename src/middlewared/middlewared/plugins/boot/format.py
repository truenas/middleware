from __future__ import annotations

import os
import shutil
import tempfile
from typing import TYPE_CHECKING, Literal

from truenas_os_pyutils.mount import umount

from middlewared.service import CallError
from middlewared.utils import run

from .disks import get_boot_type

if TYPE_CHECKING:
    from middlewared.service import ServiceContext
    from middlewared.utils.boot.models import BootFormatOptions


async def legacy_schema(context: ServiceContext, disk: str) -> Literal["BIOS_ONLY", "EFI_ONLY"] | None:
    partitions = await context.middleware.call("disk.list_partitions", disk)
    swap_types = [
        "516e7cb5-6ecf-11d6-8ff8-00022d09712b",  # used by freebsd
        "0657fd6d-a4ab-43c4-84e5-0933c84b4f4f",  # used by linux
    ]
    partitions_without_swap = [p for p in partitions if p["partition_type"] not in swap_types]
    if get_boot_type() == "EFI" and len(partitions_without_swap) == 2 and partitions[0]["size"] == 524288:
        return "BIOS_ONLY"
    elif len(partitions_without_swap) == 2 and partitions[0]["size"] == 272629760:
        return "EFI_ONLY"
    return None


async def format_disk(context: ServiceContext, dev: str, options: BootFormatOptions) -> None:
    """Format a given disk ``dev`` using the appropriate partition layout."""
    wipe_job = await context.middleware.call("disk.wipe", dev, "QUICK")
    await wipe_job.wait()
    if wipe_job.error:
        raise CallError(wipe_job.error)

    disk_details = await context.middleware.call("device.get_disk", dev)
    if not disk_details:
        raise CallError(f"Details for {dev} not found.")

    commands: list[list[str]] = []
    partitions: list[tuple[str, int]] = []
    if options.legacy_schema == "BIOS_ONLY":
        partitions.extend(
            [
                ("BIOS boot partition", 524288),
            ]
        )
    elif options.legacy_schema == "EFI_ONLY":
        partitions.extend(
            [
                ("EFI System", 272629760),
            ]
        )
    else:
        partitions.extend(
            [
                ("BIOS boot partition", 1048576),  # We allot 1MiB to bios boot partition
                ("EFI System", 536870912),  # We allot 512MiB for EFI partition
            ]
        )
    if options.size:
        partitions.append(("Solaris /usr & Mac ZFS", options.size))

    # 73 sectors are reserved by Linux for GPT tables and
    # our 4096 bytes alignment offset for the boot disk
    partitions.append(("GPT partition table", 73 * disk_details["sectorsize"]))
    total_partition_size = sum(map(lambda y: y[1], partitions))
    if disk_details["size"] < total_partition_size:
        partition_strs = [
            "%s: %s blocks" % (p[0], "{:,}".format(p[1] // disk_details["sectorsize"])) for p in partitions
        ]
        partition_strs.append("total of %s blocks" % "{:,}".format(total_partition_size // disk_details["sectorsize"]))
        disk_blocks = "{:,}".format(disk_details["blocks"])
        raise CallError(
            f"The new device ({dev}, {disk_details['size'] / (1024**3)} GB, {disk_blocks} blocks) "
            f"does not have enough space to to hold the required new partitions ({', '.join(partition_strs)}). "
            "New mirrored devices might require more space than existing devices due to changes in the "
            "booting procedure."
        )

    zfs_part_size = f"+{options.size // 1024}K" if options.size else 0
    if options.legacy_schema:
        if options.legacy_schema == "BIOS_ONLY":
            commands.extend(
                (["sgdisk", f"-a{4096 // disk_details['sectorsize']}", "-n1:0:+512K", "-t1:EF02", f"/dev/{dev}"],)
            )
        elif options.legacy_schema == "EFI_ONLY":
            commands.extend(
                (["sgdisk", f"-a{4096 // disk_details['sectorsize']}", "-n1:0:+260M", "-t1:EF00", f"/dev/{dev}"],)
            )

        # Creating standard-size partitions first leads to better alignment and more compact disk usage
        # and can help to fit larger data partition.
        commands.extend(
            [
                ["sgdisk", f"-n2:0:{zfs_part_size}", "-t2:BF01", f"/dev/{dev}"],
            ]
        )
    else:
        commands.extend(
            (
                ["sgdisk", f"-a{4096 // disk_details['sectorsize']}", "-n1:0:+1024K", "-t1:EF02", f"/dev/{dev}"],
                ["sgdisk", "-n2:0:+524288K", "-t2:EF00", f"/dev/{dev}"],
            )
        )

        # Creating standard-size partitions first leads to better alignment and more compact disk usage
        # and can help to fit larger data partition.
        commands.extend([["sgdisk", f"-n3:0:{zfs_part_size}", "-t3:BF01", f"/dev/{dev}"]])

    for command in commands:
        p = await run(*command, check=False)
        if p.returncode != 0:
            raise CallError(
                "{} failed:\n{}{}".format(" ".join(command), p.stdout.decode("utf-8"), p.stderr.decode("utf-8"))
            )

    await context.middleware.call("device.settle_udev_events")


async def install_loader(context: ServiceContext, dev: str) -> None:
    schema = await legacy_schema(context, dev)

    if schema == "EFI_ONLY":
        efi_partition_number = 1
    else:
        efi_partition_number = 2
        await run("grub-install", "--target=i386-pc", f"/dev/{dev}")

    if schema == "BIOS_ONLY":
        return

    partition = await context.middleware.call("disk.get_partition_for_disk", dev, efi_partition_number)
    await run("mkdosfs", "-F", "32", "-s", "1", "-n", "EFI", f"/dev/{partition}")
    with tempfile.TemporaryDirectory() as tmpdirname:
        efi_dir = os.path.join(tmpdirname, "efi")
        await context.to_thread(os.makedirs, efi_dir)
        await run("mount", "-t", "vfat", f"/dev/{partition}", efi_dir)
        grub_cmd = [
            "grub-install",
            "--target=x86_64-efi",
            f"--efi-directory={efi_dir}",
            "--bootloader-id=debian",
            "--recheck",
            "--no-floppy",
        ]
        if not await context.to_thread(os.path.exists, "/sys/firmware/efi"):
            grub_cmd.append("--no-nvram")
        await run(*grub_cmd)
        mounted_efi_dir = os.path.join(efi_dir, "EFI")
        await context.to_thread(os.makedirs, os.path.join(mounted_efi_dir, "boot"), exist_ok=True)
        shutil.copy(
            os.path.join(mounted_efi_dir, "debian/grubx64.efi"), os.path.join(mounted_efi_dir, "boot/bootx64.efi")
        )
        await context.to_thread(umount, efi_dir)
