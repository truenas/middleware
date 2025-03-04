from collections.abc import Generator
from dataclasses import dataclass
from functools import cached_property
from os import close, scandir, O_RDWR, O_EXCL, open as os_open
from re import compile as rcompile
from uuid import UUID

from .disk_io import read_gpt, wipe_disk_quick, write_gpt
from .gpt_parts import GptPartEntry

__all__ = ("DiskEntry", "__iterate_disks")

# sda, pmem0, vda, nvme0n1 but not sda1/vda1/nvme0n1p1
VALID_WHOLE_DISK = rcompile(r"^pmem\d+$|^sd[a-z]+$|^vd[a-z]+$|^nvme\d+n\d+$")


@dataclass(frozen=True, kw_only=True)
class DiskEntry:
    name: str | None = None
    """The disk's name (i.e. 'sda')"""
    devpath: str | None = None
    """The disk's /dev path (i.e. '/dev/sda')"""

    def __opener(self, relative_path: str, mode: str = "r") -> str | None:
        try:
            with open(f"/sys/block/{self.name}/{relative_path}", mode) as f:
                return f.read().strip()
        except Exception:
            pass

    @cached_property
    def lbs(self) -> int:
        """The disk's logical block size as reported by sysfs"""
        try:
            return int(self.__opener("queue/logical_block_size"))
        except Exception:
            # fallback to 512 always
            return 512

    @cached_property
    def pbs(self) -> int:
        """The disk's physical block size as reported by sysfs"""
        try:
            return int(self.__opener("queue/physical_block_size"))
        except Exception:
            # fallback to 512 always
            return 512

    @cached_property
    def size_sectors(self) -> int:
        """The disk's total size in sectors"""
        try:
            return int(self.__opener("size"))
        except Exception:
            # rare but dont crash here
            return 0

    @cached_property
    def size_bytes(self) -> int:
        """The disk's total size in bytes"""
        # Cf. include/linux/types.h
        # linux _always_ reports total size in sectors
        # as a multiple of 512 bytes regardless of disks
        # reported block size...
        return 512 * self.size_sectors

    @cached_property
    def serial(self) -> str | None:
        """The disk's serial number as reported by sysfs"""
        if not (serial := self.__opener("device/serial")):
            if serial := self.__opener("device/vpd_pg80", mode="rb"):
                serial = "".join(
                    chr(b) if 32 <= b <= 126 else "\uFFFD" for b in serial
                ).replace("\uFFFD", "")

        if not serial:
            # pmem devices have a uuid attribute that we use as serial
            serial = self.__opener("uuid")

        return serial

    @cached_property
    def lunid(self) -> str | None:
        """The disk's 'wwid' as presented in sysfs.

        NOTE: 'lunid' might be a bit of a misnomer since
            we're using the 'wwid' property of the disk
            but it is the same principle and it allows us
            to use common terms that most recognize."""
        wwid = self.__opener("device/wwid")
        if wwid is None:
            wwid = self.__opener("wwid")

        if wwid is not None:
            wwid = wwid.removeprefix("naa.").removeprefix("0x").removeprefix("eui.")

        return wwid

    @cached_property
    def model(self) -> str | None:
        """The disk's model as reported by sysfs"""
        return self.__opener("device/model")

    @cached_property
    def vendor(self) -> str | None:
        return self.__opener("device/vendor")

    @cached_property
    def firmware_revision(self) -> str | None:
        fr = self.__opener("device/rev")
        if fr is None:
            fr = self.__opener("device/firmware_rev")
        return fr

    @cached_property
    def identifier(self) -> str:
        """Return, ideally, a unique identifier for the disk.

        NOTE: If someone is using a usb 'hub', for example, then
            all bets are off the table. Those devices will often
            report duplicate serial numbers for all disks attached
            to it AND will report the same lunid. It's impossible
            for us to handle that and this is a scenario that isn't
            supported."""
        if self.serial and self.lunid:
            return f"{{serial_lunid}}{self.serial}_{self.lunid}"
        elif self.serial:
            return f"{{serial}}{self.serial}"
        else:
            return f"{{devicename}}{self.name}"

    @property
    def partitions(self, dev_fd: int | None = None) -> tuple[GptPartEntry] | None:
        """Return a tuple of `GptPartEntry` objects for any
        GPT partitions written to the disk."""
        return read_gpt(dev_fd or self.devpath)

    def wipe_quick(self, dev_fd: int | None = None) -> None:
        """Write 0's to the first and last 32MiB of the disk.
        This should remove all filesystem metadata and partition
        info."""
        if dev_fd is None:
            with open(os_open(self.devpath, O_RDWR | O_EXCL), "r+b") as f:
                wipe_disk_quick(f.fileno(), disk_size=self.size_bytes)
        else:
            wipe_disk_quick(dev_fd, disk_size=self.size_bytes)

    def format(self) -> UUID:
        """Format the disk with a ZoL GPT partition. By default,
        leaves a 2GiB or 1% (whichever is smaller) buffer at the
        end of disk to allow users the ability to replace disks
        in a zpool with a disk of nominal size."""
        dev_fd = os_open(self.devpath, O_RDWR | O_EXCL)
        try:
            self.wipe_quick(dev_fd=dev_fd)
            return write_gpt(dev_fd, self.size_sectors)
        finally:
            close(dev_fd)


def __iterate_disks() -> Generator[DiskEntry]:
    """Iterate over /dev and yield valid devices."""
    with scandir("/dev") as sdir:
        for i in filter(lambda x: VALID_WHOLE_DISK.match(x.name), sdir):
            yield DiskEntry(name=i.name, devpath=i.path)
