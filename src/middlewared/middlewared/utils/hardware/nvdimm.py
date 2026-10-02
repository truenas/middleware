"""Talk to an NVDIMM-N through the kernel, without running ``ixnvdimm``.

The module's firmware answers numbered requests. The kernel passes one through
per ``ND_IOCTL_CALL`` on ``/dev/nmemX``, which must be open read-write because
the kernel refuses that ioctl on a read-only descriptor.

Only requests that read are sent from here.
"""

from __future__ import annotations

import errno
import fcntl
import struct
import time

__all__ = ("dsm", "i2c_read")

# include/uapi/linux/ndctl.h
ND_IOCTL_CALL = 0xC0404E0A  # _IOWR('N', ND_CMD_CALL, struct nd_cmd_pkg)
NVDIMM_FAMILY_MSFT = 3
# nd_family, nd_command, nd_size_in, nd_size_out, nd_reserved2[9], nd_fw_size
ND_CMD_PKG = struct.Struct("=QQII36xI")

# Requests the firmware answers
CRITICAL_HEALTH = 10
MODULE_HEALTH = 11
ES_HEALTH = 12
I2C_READ = 27

# Registers, as (page, offset)
SPECREV = (0, 0x06)
FW_SLOT_INFO = (3, 0x42)
# High byte of each slot's two-byte firmware revision
SLOT_FWREV_HIGH = ((0, 0x08), (0, 0x0A))

# To run a request the kernel may need a 64 KiB contiguous buffer. On a system
# that has been up for a long time that allocation can fail, and the request
# comes back as EINVAL. Each attempt makes the kernel try to free memory again,
# so a request is sent up to this many times, counting the first one, before
# giving up.
MAX_ATTEMPTS = 5
RETRY_DELAY = 0.5


def dsm(fd: int, func: int, data: bytes = b"", *, need: int = 1, out_size: int = 32) -> bytes:
    """Send request `func` and return what the firmware sent back, without its 4-byte status.

    Raises ``OSError`` when the kernel rejects the call, when the firmware
    reports a failure, or when fewer than `need` bytes come back.
    """
    buf = bytearray(ND_CMD_PKG.pack(NVDIMM_FAMILY_MSFT, func, len(data), out_size, 0) + data + bytes(out_size))
    for attempt in range(MAX_ATTEMPTS):
        try:
            fcntl.ioctl(fd, ND_IOCTL_CALL, buf)
            break
        except OSError as e:
            if attempt == MAX_ATTEMPTS - 1 or e.errno != errno.EINVAL:
                raise
            time.sleep(RETRY_DELAY)

    # The output follows the input, and nd_fw_size says how much of it the firmware wrote
    start = ND_CMD_PKG.size + len(data)
    end = start + ND_CMD_PKG.unpack_from(buf)[4]
    out = bytes(buf[start:end])
    if len(out) < 4 + need or int.from_bytes(out[:4], "little"):
        raise OSError(errno.EIO, f"NVDIMM request {func} failed: {out.hex()}")
    return out[4:]


def i2c_read(fd: int, page: int, off: int) -> int:
    """Read one byte from the module's register map."""
    return dsm(fd, I2C_READ, bytes((page, off)), out_size=5)[0]
