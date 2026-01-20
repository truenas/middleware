import ctypes
import fcntl
import os
from typing import TypedDict


class InquiryResult(TypedDict):
    vendor: str
    product: str
    revision: str
    serial: str


# SG_IO ioctl command constant
SG_IO = 0x2285

# SCSI sense buffer size constant
SG_MAX_SENSE = 32

# Other necessary constants
SG_DXFER_FROM_DEV = -3
SG_DXFER_NONE = 0
SG_FLAG_DIRECT_IO = 1
SG_INFO_OK = 0

# SCSI Enclosure Services command
SES_RECEIVE_DIAGNOSTIC = 0x1C
SES_ENCLOSURE_STATUS_PAGE_CODE = 0x02
INQUIRY = 0x12


class sg_io_hdr_v3(ctypes.Structure):
    _fields_ = [
        ("interface_id", ctypes.c_int),
        ("dxfer_direction", ctypes.c_int),
        ("cmd_len", ctypes.c_ubyte),
        ("mx_sb_len", ctypes.c_ubyte),
        ("iovec_count", ctypes.c_ushort),
        ("dxfer_len", ctypes.c_uint),
        ("dxferp", ctypes.c_void_p),
        ("cmdp", ctypes.c_void_p),
        ("sbp", ctypes.c_void_p),
        ("timeout", ctypes.c_uint),
        ("flags", ctypes.c_uint),
        ("pack_id", ctypes.c_int),
        ("usr_ptr", ctypes.c_void_p),
        ("status", ctypes.c_ubyte),
        ("masked_status", ctypes.c_ubyte),
        ("msg_status", ctypes.c_ubyte),
        ("sb_len_wr", ctypes.c_ubyte),
        ("host_status", ctypes.c_ushort),
        ("driver_status", ctypes.c_ushort),
        ("resid", ctypes.c_int),
        ("duration", ctypes.c_uint),
        ("info", ctypes.c_uint),
    ]


def get_sgio_hdr_structure(
    cdb: ctypes.Array[ctypes.c_ubyte], dxfer_len: int, timeout: int = 60000
) -> tuple[sg_io_hdr_v3, ctypes.Array[ctypes.c_ubyte], ctypes.Array[ctypes.c_ubyte]]:
    # Create a buffer for the sense data
    sense_buffer = (ctypes.c_ubyte * SG_MAX_SENSE)()
    results_buffer = (ctypes.c_ubyte * dxfer_len)()

    hdr = sg_io_hdr_v3()
    hdr.interface_id = ord('S')
    hdr.cmd_len = len(cdb)
    hdr.cmdp = ctypes.cast(cdb, ctypes.c_void_p)
    hdr.dxfer_direction = SG_DXFER_FROM_DEV
    hdr.dxfer_len = dxfer_len
    hdr.dxferp = ctypes.cast(results_buffer, ctypes.c_void_p)
    hdr.sbp = ctypes.cast(sense_buffer, ctypes.c_void_p)
    hdr.mx_sb_len = len(sense_buffer)
    hdr.timeout = timeout

    return hdr, results_buffer, sense_buffer


def do_io(device: str, hdr: sg_io_hdr_v3) -> None:
    fd = os.open(device, os.O_RDONLY | os.O_NONBLOCK)
    try:
        # Make the ioctl call
        if fcntl.ioctl(fd, SG_IO, hdr) != 0:
            raise OSError("SG_IO ioctl failed")
        elif (hdr.info & SG_INFO_OK) != 0:
            raise OSError("SG_IO ioctl indicated failure")
    finally:
        # Close the device
        os.close(fd)


def inquiry(device: str) -> InquiryResult:
    dxfer_len = 0x38
    cdb = (ctypes.c_ubyte * 6)(INQUIRY, 0x00, 0x00, 0x00, dxfer_len, 0x00)
    hdr, results_buffer, sense_buffer = get_sgio_hdr_structure(cdb, dxfer_len)
    do_io(device, hdr)

    # Table 148 in SPC-5
    t10_vendor_start, t10_vendor_end, t10_final = 8, (15 + 1), ''
    product_ident_start, product_ident_end, product_ident_final = t10_vendor_end, (31 + 1), ''
    product_rev_start, product_rev_end, product_rev_final = product_ident_end, (35 + 1), ''
    serial_start, serial_end, serial_final = product_rev_end, (55 + 1), ''

    for char in results_buffer[t10_vendor_start:t10_vendor_end]:
        if (_ascii := chr(char)) in (' ', '\x00'):
            continue
        t10_final += _ascii

    for char in results_buffer[product_ident_start:product_ident_end]:
        if (_ascii := chr(char)) in (' ', '\x00'):
            continue
        product_ident_final += _ascii

    for char in results_buffer[product_rev_start:product_rev_end]:
        if (_ascii := chr(char)) in (' ', '\x00'):
            continue
        product_rev_final += _ascii

    for char in results_buffer[serial_start:serial_end]:
        if (_ascii := chr(char)) in (' ', '\x00'):
            continue
        serial_final += _ascii

    return {'vendor': t10_final, 'product': product_ident_final, 'revision': product_rev_final, 'serial': serial_final}
