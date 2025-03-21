from collections.abc import Generator
from dataclasses import dataclass
from functools import cached_property
from os import scandir, O_RDWR, O_EXCL, open as os_open
from re import compile as rcompile

from .disk_io import read_gpt, wipe_disk_quick
from .gpt_parts import GptPartEntry

__all__ = ("DiskEntry", "iterate_disks")

# sda, pmem0, vda, nvme0n1 but not sda1/vda1/nvme0n1p1
VALID_WHOLE_DISK = rcompile(r"^pmem\d+$|^sd[a-z]+$|^vd[a-z]+$|^nvme\d+n\d+$")


@dataclass(frozen=True, slots=True, kw_only=True)
class TempEntry:
    temp_c: float | None = None
    """The current temperature in celsius"""
    crit: float | None = None
    """This value is reported as celsius.

    For SCSI drives (as described in SPC-6):
        The REFERENCE TEMPERATURE field indicates
        the maximum reported sensor temperature in
        degrees Celsius at which the SCSI target
        device is capable of operating continuously
        without degrading the SCSI target device's
        operation or reliability beyond manufacturer
        accepted limits.

    For NVMe drives (as described in base spec 2.0e)
        The critical composite temperature threshold
        (CCTEMP) field. This field indicates the
        minimum Composite Temperature field value that
        indicates a critical overheating condition
        (e.g., may prevent continued normal operation,
            possibility of data loss, automatic device
            shutdown, extreme performance throttling,
            or permanent damage)

    For ATA drives (as described in ATA/ATAPI Command Set)
        The "Over Limit" field (byte 7) represents the
        maximum temperature limit. Operating the device
        over this temperature may cause physical damage to
        the device.
    """


@dataclass(frozen=True, kw_only=True)
class DiskEntry:
    name: str | None = None
    """The disk's name (i.e. 'sda')"""
    devpath: str | None = None
    """The disk's /dev path (i.e. '/dev/sda')"""

    def __opener(
        self,
        *,
        relative_path: str | None = None,
        absolute_path: str | None = None,
        mode: str = "r",
    ) -> str | None:
        if relative_path is None and absolute_path is None:
            raise ValueError("relative_path or absolute_path is required")

        try:
            with open(relative_path or absolute_path, mode) as f:
                return f.read().strip()
        except Exception:
            pass

    @cached_property
    def lbs(self) -> int:
        """The disk's logical block size as reported by sysfs"""
        try:
            return int(self.__opener(relative_path="queue/logical_block_size"))
        except Exception:
            # fallback to 512 always
            return 512

    @cached_property
    def pbs(self) -> int:
        """The disk's physical block size as reported by sysfs"""
        try:
            return int(self.__opener(relative_path="queue/physical_block_size"))
        except Exception:
            # fallback to 512 always
            return 512

    @cached_property
    def size_sectors(self) -> int:
        """The disk's total size in sectors"""
        # Cf. include/linux/types.h
        # The kernel represents the disk
        # size in units of 512 bytes always
        # regardless of the disk's reported
        # block size.
        try:
            return int(self.__opener(relative_path="size"))
        except Exception:
            # rare but dont crash here
            return 0

    @cached_property
    def size_bytes(self) -> int:
        """The disk's total size in bytes"""
        # Cf. include/linux/types.h
        # The kernel represents the disk
        # size in units of 512 bytes always
        # regardless of the disk's reported
        # block size.
        return 512 * self.size_sectors

    @cached_property
    def serial(self) -> str | None:
        """The disk's serial number as reported by sysfs"""
        if not (serial := self.__opener(relative_path="device/serial")):
            if serial := self.__opener(relative_path="device/vpd_pg80", mode="rb"):
                serial = "".join(
                    chr(b) if 32 <= b <= 126 else "\ufffd" for b in serial
                ).replace("\ufffd", "")

        if not serial:
            # pmem devices have a uuid attribute that we use as serial
            serial = self.__opener(relative_path="uuid")

        return serial

    @cached_property
    def lunid(self) -> str | None:
        """The disk's 'wwid' as presented in sysfs.

        NOTE: 'lunid' might be a bit of a misnomer since
            we're using the 'wwid' property of the disk
            but it is the same principle and it allows us
            to use common terms that most recognize."""
        wwid = self.__opener(relative_path="device/wwid")
        if wwid is None:
            wwid = self.__opener(relative_path="wwid")

        if wwid is not None:
            wwid = wwid.removeprefix("naa.").removeprefix("0x").removeprefix("eui.")

        return wwid

    @cached_property
    def model(self) -> str | None:
        """The disk's model as reported by sysfs"""
        return self.__opener(relative_path="device/model")

    @cached_property
    def vendor(self) -> str | None:
        return self.__opener(relative_path="device/vendor")

    @cached_property
    def firmware_revision(self) -> str | None:
        fr = self.__opener(relative_path="device/rev")
        if fr is None:
            fr = self.__opener(relative_path="device/firmware_rev")
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

    def temp(self) -> TempEntry:
        """Return temperature information as reported via sysfs.
        This information is obtained via the drivetemp kernel
        module.

        NOTE: The `temp1_input` file will issue a command to the
        disk each time it's accessed from user-space. It's the
        callers responsibility to ensure this value is accessed
        at a frequency that makes sense."""
        base = f"/sys/block/{self.name}"
        if "nvme" in self.name:
            path = f"{base}/device"
        else:
            path = f"{base}/device/hwmon"

        rv = {"temp_c": None, "crit": None}
        try:
            with scandir(path) as sdir:
                for i in filter(
                    lambda x: x.is_dir() and x.name.startswith("hwmon"), sdir
                ):
                    try:
                        name = self.__opener(absolute_path=f"{i.path}/name")
                        if name not in ("nvme", "drivetemp"):
                            continue
                    except Exception:
                        continue

                    try:
                        milli_c = int(
                            self.__opener(absolute_path=f"{i.path}/temp1_input")
                        )
                    except (ValueError, FileNotFoundError):
                        continue
                    else:
                        # sysfs values are stored in millidegrees celsius
                        rv["temp_c"] = milli_c / 1000

                    try:
                        crit = int(self.__opener(absolute_path=f"{i.path}/temp1_crit"))
                    except (ValueError, FileNotFoundError):
                        continue
                    else:
                        # syfs values are stored in millidegrees celsius
                        rv["crit"] = crit / 1000
        except FileNotFoundError:
            # pmem devices dont have this, for example
            pass

        return TempEntry(**rv)

    @property
    def partitions(self, dev_fd: int | None = None) -> tuple[GptPartEntry] | None:
        """Return a tuple of `GptPartEntry` objects for any
        GPT partitions written to the disk."""
        return read_gpt(dev_fd or self.devpath, self.lbs)

    def wipe_quick(self, dev_fd: int | None = None) -> None:
        """Write 0's to the first and last 32MiB of the disk.
        This should remove all filesystem metadata and partition
        info."""
        if dev_fd is None:
            with open(os_open(self.devpath, O_RDWR | O_EXCL), "r+b") as f:
                wipe_disk_quick(f.fileno(), disk_size=self.size_bytes)
        else:
            wipe_disk_quick(dev_fd, disk_size=self.size_bytes)


def iterate_disks() -> Generator[DiskEntry]:
    """Iterate over /dev and yield valid devices."""
    with scandir("/dev") as sdir:
        for i in filter(lambda x: VALID_WHOLE_DISK.match(x.name), sdir):
            yield DiskEntry(name=i.name, devpath=i.path)
