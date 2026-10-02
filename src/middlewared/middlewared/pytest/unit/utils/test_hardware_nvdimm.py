"""Coverage for the NVDIMM request helper, with a stand-in for the kernel's ``ND_IOCTL_CALL``."""

import errno
import struct

import pytest

from middlewared.utils.hardware import nvdimm

OK = bytes(4)
"""The status the firmware puts ahead of its answer when the request worked."""


@pytest.fixture
def kernel(monkeypatch):
    """Answer each request in turn the way the kernel does: the reply lands after
    the input and its length goes in ``nd_fw_size``. A reply that is an
    ``OSError`` is raised instead. Returns the requests that were sent."""

    def build(*replies):
        pending = list(replies)
        requests = []

        def ioctl(fd, request, buf):
            family, func, size_in, size_out, _ = nvdimm.ND_CMD_PKG.unpack_from(buf)
            head = nvdimm.ND_CMD_PKG.size
            start = head + size_in
            assert request == nvdimm.ND_IOCTL_CALL
            assert family == nvdimm.NVDIMM_FAMILY_MSFT
            assert len(buf) == start + size_out
            requests.append((func, bytes(buf[head:start])))

            reply = pending.pop(0)
            if isinstance(reply, OSError):
                raise reply

            copied = reply[:size_out]
            end = start + len(copied)
            buf[start:end] = copied
            struct.pack_into("=I", buf, 60, len(reply))
            return 0

        monkeypatch.setattr(nvdimm.fcntl, "ioctl", ioctl)
        monkeypatch.setattr(nvdimm.time, "sleep", lambda seconds: None)
        return requests

    return build


def test_ioctl_number_matches_the_kernel_header():
    """``_IOWR('N', 10, struct nd_cmd_pkg)``, and the struct is 64 bytes."""
    assert nvdimm.ND_CMD_PKG.size == 64
    assert nvdimm.ND_IOCTL_CALL == 3 << 30 | 64 << 16 | ord("N") << 8 | 10


def test_dsm_returns_the_answer_without_its_status(kernel):
    requests = kernel(OK + b"\x44")

    assert nvdimm.dsm(3, nvdimm.CRITICAL_HEALTH) == b"\x44"
    assert requests == [(nvdimm.CRITICAL_HEALTH, b"")]


def test_i2c_read_sends_page_and_offset(kernel):
    requests = kernel(OK + b"\x22")

    assert nvdimm.i2c_read(3, *nvdimm.SPECREV) == 0x22
    assert requests == [(nvdimm.I2C_READ, bytes(nvdimm.SPECREV))]


def test_firmware_failure_status_raises(kernel):
    kernel(b"\x01\x00\x00\x00\x44")

    with pytest.raises(OSError):
        nvdimm.dsm(3, nvdimm.CRITICAL_HEALTH)


def test_short_answer_raises(kernel):
    kernel(OK + bytes(6))

    with pytest.raises(OSError):
        nvdimm.dsm(3, nvdimm.MODULE_HEALTH, need=7)


def test_einval_is_retried_once(kernel):
    requests = kernel(OSError(errno.EINVAL, "Invalid argument"), OK + b"\x44")

    assert nvdimm.dsm(3, nvdimm.CRITICAL_HEALTH) == b"\x44"
    assert len(requests) == 2


def test_einval_on_every_attempt_propagates(kernel):
    failures = [OSError(errno.EINVAL, "Invalid argument")] * nvdimm.MAX_ATTEMPTS
    requests = kernel(*failures)

    with pytest.raises(OSError) as e:
        nvdimm.dsm(3, nvdimm.CRITICAL_HEALTH)

    assert e.value.errno == errno.EINVAL
    assert len(requests) == nvdimm.MAX_ATTEMPTS


def test_other_errors_are_not_retried(kernel):
    """ENOTTY is the kernel saying this firmware does not answer that request at all."""
    requests = kernel(OSError(errno.ENOTTY, "Inappropriate ioctl for device"))

    with pytest.raises(OSError):
        nvdimm.i2c_read(3, *nvdimm.SPECREV)

    assert len(requests) == 1
