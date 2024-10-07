from dataclasses import dataclass

from .maps import PeripheralDeviceType
from middlewared.utils.system.disks.exceptions import (
    DataLengthError,
    FileTooShort,
    MismatchHeaderType,
    UnsupportedPage,
)

__all__ = (
    "HeaderInfo",
    "validate_and_parse_header",
)

SUPPORTED_PAGES: tuple[int] = (0x80, 0x83)
HEADER_LENGTH: int = 4


@dataclass(slots=True, frozen=True, kw_only=True)
class HeaderInfo:
    peripheral_device_type: str
    peripheral_qualifier: int
    page_length: int
    header_length: int


def validate_and_parse_header(data: memoryview, vpd_page: int) -> HeaderInfo:
    if vpd_page not in SUPPORTED_PAGES:
        raise UnsupportedPage(
            f"VPD Page {hex(vpd_page)} unsupported. Expect 1 of {','.join(SUPPORTED_PAGES)}."
        )
    elif data.nbytes < HEADER_LENGTH:
        raise FileTooShort(f"File too short for VPD Page {hex(vpd_page)}")

    header: memoryview = data[:HEADER_LENGTH]
    if header[1] != vpd_page:
        raise MismatchHeaderType(
            f"Unexpected page code: {hex(header[1])}, expected {hex(vpd_page)}."
        )

    page_length: int = int.from_bytes(header[2:4], byteorder="big")
    if page_length + HEADER_LENGTH != data.nbytes:
        raise DataLengthError("Unexpected data length.")

    peripheral_qualifier: int = header[0] >> 5
    try:
        peripheral_device_type: str = PeripheralDeviceType[header[0] & 0x1F]
    except KeyError:
        peripheral_device_type: str = PeripheralDeviceType[31]

    return HeaderInfo(
        peripheral_device_type=peripheral_device_type,
        peripheral_qualifier=peripheral_qualifier,
        page_length=page_length,
        header_length=HEADER_LENGTH,
    )
