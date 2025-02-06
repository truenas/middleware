from collections.abc import Generator
from dataclasses import dataclass
from os import scandir
from re import compile as rcompile

from pyudev import Context, Devices, DeviceNotFoundByNameError

# sda, pmem0, vda, nvme0n1 but not sda1/vda1/nvme0n1p1
VALID_WHOLE_DISK = rcompile(r"^pmem\d+$|^sd[a-z]+$|^vd[a-z]+$|^nvme\d+n\d+$")


@dataclass(slots=True, frozen=True, kw_only=True)
class DiskEntry:
    name: str | None = None
    """The disk name (i.e. 'sda')"""
    devpath: str | None = None
    """The disk /dev path (i.e. '/dev/sda')"""
    serial: str | None = None
    """The disk serial number as reported by udevd"""
    lunid: str | None = None
    """The 'lunid' as presented by udevd.

    NOTE: 'lunid' might be a bit of a misnomer since
        we're using the 'ID_WWN' property of the disk
        but it is the same principle and it allows us
        to use common terms that most recognize."""

    @property
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


def __get_disks_impl() -> Generator[tuple[str, str]]:
    """Iterate over /dev and yield valid devices."""
    with scandir("/dev") as sdir:
        for i in filter(lambda x: VALID_WHOLE_DISK.match(x.name), sdir):
            yield i.name, i.path


def __get_serial_lunid(ctx: Context, devname: str) -> tuple[str | None, str | None]:
    serial = lunid = None
    try:
        dev = Devices.from_name(ctx, "block", devname)
    except DeviceNotFoundByNameError:
        # disk could have been yanked
        # (or died) by the time we
        # enumerated the path
        return serial, lunid

    # order of these keys are important
    for key in ("ID_SCSI_SERIAL", "ID_SERIAL_SHORT", "ID_SERIAL"):
        try:
            serial = dev.properties[key]
            break
        except KeyError:
            continue

    try:
        lunid = dev.properties["ID_WWN"].removeprefix("0x").removeprefix("eui.")
    except (KeyError, AttributeError):
        pass

    return serial, lunid
