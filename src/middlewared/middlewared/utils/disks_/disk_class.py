import collections
import contextlib
import dataclasses
import errno
import functools
import json
import logging
import os
import re
import string
import subprocess
import typing
import uuid

from .disk_io import read_gpt, wipe_disk_quick, create_gpt_partition
from .gpt_parts import GptPartEntry, PART_TYPES

logger = logging.getLogger(__name__)

__all__ = ("DiskEntry", "iterate_disks", "VALID_WHOLE_DISK")

# sda, pmem0, vda, xvda, nvme0n1 but not sda1/vda1/xvda1/nvme0n1p1
VALID_WHOLE_DISK = re.compile(r"^pmem\d+$|sd[a-z]+$|^vd[a-z]+$|^xvd[a-z]+$|^nvme\d+n\d+$")


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
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


@dataclasses.dataclass(frozen=True, kw_only=True)
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

        if relative_path is not None:
            path = f"/sys/block/{self.name}/{relative_path}"
        else:
            path = absolute_path

        try:
            with open(path, mode) as f:
                return f.read().strip()
        except Exception:
            pass

    @functools.cached_property
    def lbs(self) -> int:
        """The disk's logical block size as reported by sysfs"""
        try:
            return int(self.__opener(relative_path="queue/logical_block_size"))
        except Exception:
            # fallback to 512 always
            return 512

    @functools.cached_property
    def pbs(self) -> int:
        """The disk's physical block size as reported by sysfs"""
        try:
            return int(self.__opener(relative_path="queue/physical_block_size"))
        except Exception:
            # fallback to 512 always
            return 512

    @functools.cached_property
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

    @functools.cached_property
    def size_bytes(self) -> int:
        """The disk's total size in bytes"""
        # Cf. include/linux/types.h
        # The kernel represents the disk
        # size in units of 512 bytes always
        # regardless of the disk's reported
        # block size.
        return 512 * self.size_sectors

    @functools.cached_property
    def serial(self) -> str | None:
        """The disk's serial number as reported by sysfs"""
        # nvme devices
        serial = self.__opener(relative_path="device/serial")
        if not serial:
            # virtio-blk devices (vd)
            serial = self.__opener(relative_path="serial")

        if not serial:
            if raw := self.__opener(relative_path="device/vpd_pg80", mode="rb"):
                # VPD page 0x80 (Unit Serial Number) structure:
                #   Byte 0: Peripheral qualifier & device type
                #   Byte 1: Page code (0x80)
                #   Bytes 2-3: Page length (16-bit big-endian)
                #   Bytes 4+: ASCII serial-number data
                #
                # Reference: SCSI Primary Commands (SPC-7 rev 1) — Unit Serial Number VPD page 0x80, Table 599
                if len(raw) >= 4:
                    # unit serial page (vpd_pg80) command can never be > 255 characters
                    # So we will grab page length from 3
                    # Guard against devices that report a length larger than the buffer
                    page_len = min(raw[3], len(raw) - 4)

                    # Extract only the serial number data, skipping the 4-byte header
                    serial_txt = raw[4:4 + page_len].decode('ascii', errors='ignore')
                    serial = serial_txt.rstrip('\x00').strip()
                else:
                    serial = ""

        if not serial:
            # pmem devices have a uuid attribute that we use as serial
            serial = self.__opener(relative_path="uuid")

        # strip is required because we see these cases otherwise
        # >>> d.serial reported as '        3FJ1U1HT'
        return serial.strip() if serial else None

    @functools.cached_property
    def lunid(self) -> str | None:
        """The disk's 'wwid' as presented in sysfs.

        NOTE: 'lunid' might be a bit of a misnomer since
            we're using the 'wwid' property of the disk
            but it is the same principle and it allows us
            to use common terms that most recognize."""
        HEX = set(string.hexdigits.lower())

        wwid = self.__opener(relative_path="device/wwid")
        if wwid is None:
            wwid = self.__opener(relative_path="wwid")

        if wwid is not None:
            # Normalize: strip whitespace and convert to lowercase
            wwid = wwid.strip().lower()

            # udev handling of WWN identifiers:
            # - For SCSI devices: ID_WWN is set only for NAA descriptors (via scsi_id)
            # - For NVMe devices: ID_WWN is set to the wwid sysfs value, which includes eui. prefix
            #   (see /usr/lib/udev/rules.d/60-persistent-storage.rules)
            # - For both: The middleware strips prefixes to get a consistent format
            #
            # We strip naa., 0x, and eui. prefixes to match middleware behavior.
            # t10 identifiers are not used for ID_WWN and return None.
            original_prefix = None
            for prefix in ("naa.", "0x", "eui."):
                if wwid.startswith(prefix):
                    original_prefix = prefix
                    wwid = wwid[len(prefix):]
                    break
            else:
                # t10.* and others are not used for ID_WWN in udev
                return None

            # Remove spaces after prefix stripping
            wwid = wwid.replace(" ", "")

            # Truncate to 16 characters ONLY for NAA WWNs with valid hex characters.
            # This matches udev's ID_WWN behavior for NAA WWNs specifically.
            # EUI identifiers (common for NVMe) are NOT truncated.
            #
            # Reference: https://github.com/systemd/systemd/blob/e65455feade65c798fd1742220768eba7f81755b/
            # src/udev/scsi_id/scsi_serial.c
            # check_fill_0x83_id(): if (id_search->id_type == SCSI_ID_NAA && wwn != NULL)
            #                       strncpy(wwn, serial + s, 16);
            if original_prefix in ("naa.", "0x") and len(wwid) > 16 and set(wwid[:16]) <= HEX:
                wwid = wwid[:16]

        return wwid if wwid else None

    @functools.cached_property
    def model(self) -> str | None:
        """The disk's model as reported by sysfs"""
        return self.__opener(relative_path="device/model")

    @functools.cached_property
    def vendor(self) -> str | None:
        return self.__opener(relative_path="device/vendor")

    @functools.cached_property
    def firmware_revision(self) -> str | None:
        fr = self.__opener(relative_path="device/rev")
        if fr is None:
            fr = self.__opener(relative_path="device/firmware_rev")
        return fr

    @functools.cached_property
    def media_type(self) -> str:
        fr = self.__opener(relative_path="queue/rotational")
        return "HDD" if fr == "1" else "SSD"

    @functools.cached_property
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
        elif partitions := self.partitions():
            with contextlib.suppress(Exception):
                # We don't want to crash if we can't read partitions
                for part in filter(
                    lambda p: PART_TYPES.get(p.partition_type_guid, "UNKNOWN") == "ZFS",
                    partitions
                ):
                    return f"{{uuid}}{part.unique_partition_guid}"

        # If we reach here, we have no serial or partitions
        return f"{{devicename}}{self.name}"

    @functools.cached_property
    def translation(self) -> typing.Literal["SATL", "SNTL", None]:
        """Determine if the disk is using translation.

        Returns:

        SATL: (S)CSI-(A)TA (T)ranslation (L)ayer ATA devices
            that sit behind a SCSI device.

        SNTL: (S)CSI-(N)VMe (T)ranslation (L)ayer NVMe devices
            that sit behind a SCSI(SAS) device.

            NOTE: THIS IS NOT A REAL SPECIFICATION. We
            just use it internally. (tri-mode HBAs are "fun")

        None: No translation.
        """
        if os.path.exists(f"/sys/block/{self.name}/vpd_pg89"):
            return "SATL"
        elif self.name.startswith("sd") and self.vendor == "NVMe":
            return "SNTL"
        return None

    def __run_smartctl_cmd_impl(self, cmd: list[str], raise_alert: bool = True) -> str:
        if tl := self.translation:
            if tl == "SATL":
                cmd.extend(["-d", "sat"])
            elif tl == "SNTL":
                cmd.extend(["-d", "nvme"])

        cp = subprocess.run(
            cmd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf8",
            errors="ignore",
        )
        if (cp.returncode & 0b11) != 0:
            if raise_alert:
                raise OSError(f"{cmd!r} failed for {self.name} ({cp.returncode!r}):\n{cp.stderr}")
        return cp.stdout

    def smartctl_info(self, return_json: bool = False, raise_alert: bool = True) -> dict | str:
        """Return smartctl -x information.

        Args:
            return_json: If True, will return JSON serialized results.
                        If False, returns raw string output.

        Returns:
            dict | str: Parsed JSON dict if return_json=True, raw string otherwise.
        """
        cmd = ["smartctl", "-x", self.devpath]
        if return_json:
            cmd.extend(["-jc"])

        stdout = self.__run_smartctl_cmd_impl(cmd, raise_alert)
        if return_json:
            return json.loads(stdout)
        else:
            return stdout

    def smartctl_test(
        self, ttype: typing.Literal["long", "short", "offline", "conveyance"], raise_alert: bool = True
    ) -> None:
        """Run a SMART test.

        ttype: str The type of SMART test to be ran.
        """
        self.__run_smartctl_cmd_impl(["smartctl", self.devpath, "-t", ttype], raise_alert)

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
            with os.scandir(path) as sdir:
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
                    except Exception:
                        # if we can't get the temperature
                        # then there is no reason to try
                        # the other sysfs files.
                        continue
                    else:
                        # sysfs values are stored in millidegrees celsius
                        rv["temp_c"] = milli_c / 1000

                    try:
                        crit = int(self.__opener(absolute_path=f"{i.path}/temp1_crit"))
                    except Exception:
                        pass
                    else:
                        # syfs values are stored in millidegrees celsius
                        rv["crit"] = crit / 1000
        except FileNotFoundError:
            # pmem devices dont have this, for example
            pass

        return TempEntry(**rv)

    def partitions(self, dev_fd: int | None = None) -> tuple[GptPartEntry] | None:
        """Return a tuple of `GptPartEntry` objects for any
        GPT partitions written to the disk."""
        try:
            return read_gpt(dev_fd or self.devpath, self.lbs)
        except Exception as e:
            if isinstance(e, OSError) and e.errno == errno.ENOMEDIUM:
                # when we access the "identifier" attribute of the disk object
                # we try to read partitions on the devices which requires
                # opening the underlying device. Our users run TrueNAS
                # on extravagant hardware and, sometimes, the devices dont
                # respond very well to even opening them in RD_ONLY mode.
                # For example, opening an empty sd-card reader device
                # raises errno 123 (no medimum found). In this scenario
                # and any other, we should not crash here.
                pass
            else:
                logger.exception("Unexpected error reading partitions for device: %r", self.devpath)

    def wipe_quick(self, dev_fd: int | None = None) -> None:
        """Write 0's to the first and last 32MiB of the disk.
        This should remove all filesystem metadata and partition
        info."""
        if dev_fd is None:
            with open(os.open(self.devpath, os.O_RDWR | os.O_EXCL), "r+b") as f:
                wipe_disk_quick(f.fileno(), disk_size=self.size_bytes)
        else:
            wipe_disk_quick(dev_fd, disk_size=self.size_bytes)

    def format(self) -> uuid.UUID:
        """Format the disk with a GPT partition table containing a single ZFS partition.

        Creates a complete GPT (GUID Partition Table) structure on the disk,
        including protective MBR, primary and secondary GPT headers, and partition entries.
        The partition is configured for ZFS use with proper alignment and sizing.

        This method automatically wipes any existing partitions before creating the new
        GPT structure. It opens the device once and reuses the file descriptor for all
        operations to optimize performance.

        Returns:
            uuid.UUID: The unique identifier (GUID) of the created partition

        Raises:
            ValueError: If there's insufficient space on the disk after applying
                       alignment constraints
            OSError: If the device cannot be opened or accessed

        Note:
            - The device must not be mounted or in use
            - Requires root privileges to access block devices
            - Automatically wipes existing partitions if present
            - Creates a single partition spanning most of the disk with proper alignment
            - Reserves space at the end of the disk for resilience (up to 2GB or 1% of disk)
            - Uses 1MB alignment for optimal performance
            - For 4K native disks, uses sector 2048 as the first usable sector
            - Opens device only once for optimal performance
        """
        dev_fd = os.open(self.devpath, os.O_RDWR | os.O_EXCL)
        try:
            if self.partitions(dev_fd):
                # existing partitions detected
                # so we need to wipe them before
                # we format the disk with new ones
                self.wipe_quick(dev_fd)
            return create_gpt_partition(
                dev_fd,
                ts_512=self.size_sectors,
                lbs=self.lbs,
                pbs=self.pbs,
            )
        finally:
            os.close(dev_fd)


def iterate_disks() -> collections.abc.Generator[DiskEntry]:
    """Iterate over /dev and yield valid devices."""
    with os.scandir("/dev") as sdir:
        for i in filter(lambda x: VALID_WHOLE_DISK.match(x.name), sdir):
            yield DiskEntry(name=i.name, devpath=i.path)
