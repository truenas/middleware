import contextlib
import logging
import os
import textwrap

from middlewared.service import job, private, Service
from middlewared.utils import run

logger = logging.getLogger(__name__)


class UpdateService(Service):
    @private
    @job()
    async def freebsd_to_scale(self):
        logger.info("Updating FreeBSD installation to SCALE")

        with contextlib.suppress(FileNotFoundError):
            os.unlink("/data/freebsd-to-scale-update")

        await self.middleware.call("etc.generate", "fstab", "initial")
        await run(["mount", "-a"])

        await self.middleware.call("etc.generate", "rc")
        await self.middleware.call("boot.update_initramfs")
        await self.middleware.call("etc.generate", "grub")

        await self.middleware.call("system.reboot")

    @private
    async def freebsd_grub(self):
        pool_name = await self.middleware.call("boot.pool_name")
        for dataset in await self.middleware.call("zfs.dataset.query", [["name", "^", f"{pool_name}/"]]):
            if dataset["properties"].get("truenas:12", {}).get("value") == "1":
                freebsd_root_dataset = dataset["name"]
                break
        else:
            return ""

        if (
            await self.middleware.call("zfs.pool.query", [["name", "=", pool_name]], {"get": True})
        )["properties"]["bootfs"]["value"] != dataset["name"]:
            # Grub can only boot FreeBSD if pool `bootfs` is set to FreeBSD dataset
            return ""

        if await self.middleware.call("boot.get_boot_type") == "BIOS":
            bsd_loader = f"""\
                insmod zfs
                search -s -l {pool_name}
                kfreebsd /{"/".join(freebsd_root_dataset.split("/")[1:])}@/boot/loader
            """
        else:
            disks = await self.middleware.call("boot.get_disks")
            partition = await self.middleware.call("disk.get_partition_for_disk", disks[0], 1)
            efi_partition_uuid = (await run(["grub-probe", "--device", f"/dev/{partition}", "--target=fs_uuid"],
                                            encoding="utf-8", errors="ignore")).stdout.strip()
            bsd_loader = f"""\
                insmod zfs
                insmod search_fs_uuid
                insmod chain
                search --fs-uuid --no-floppy --set=root {efi_partition_uuid}
                chainloader ($root)/efi/boot/FreeBSD.efi
            """

        return textwrap.dedent(f"""\
            menuentry "TrueNAS CORE" {{
                insmod part_gpt
                {bsd_loader}
            }}
        """)
