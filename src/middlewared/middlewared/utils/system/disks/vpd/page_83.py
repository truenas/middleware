from dataclasses import dataclass
from types import NoneType

from .maps import (
    AssociationField,
    CodeSetField,
    DesignatorTypeField,
    NAAFormats,
    ProtocolIdentifierField,
)
from .header import HeaderInfo, validate_and_parse_header
from middlewared.utils.system.disks.exceptions import DataLengthError


@dataclass(slots=True, frozen=True, kw_only=True)
class DesignatorHeader:
    protocol_identifier: str
    code_set: str
    piv: int
    association: str
    designator_type: str
    designator_length: int


@dataclass(slots=True, frozen=True, kw_only=True)
class Designator:
    designator_header: DesignatorHeader
    naa_type: int | None = None
    naa_format: str | None = None
    parsed: str


@dataclass(slots=True, frozen=True, kw_only=True)
class Pg83:
    header: HeaderInfo
    designators: tuple[Designator]


def parse_designator_header(descriptor_header: memoryview) -> DesignatorHeader:
    try:
        code_set: str = CodeSetField[descriptor_header[0] & 0x0F]
    except KeyError:
        # wut...
        code_set: NoneType = None

    try:
        protocol_identifier: str = ProtocolIdentifierField[descriptor_header[0] >> 4]
    except ValueError:
        protocol_identifier: NoneType = None

    try:
        designator_type: str = DesignatorTypeField[descriptor_header[1] & 0x0F]
    except ValueError:
        designator_type: NoneType = None

    try:
        association: str = AssociationField[(descriptor_header[1] & 0x30) >> 4]
    except ValueError:
        association: NoneType = None

    piv: int = descriptor_header[0] & 0x80
    designator_length: int = descriptor_header[3]

    return DesignatorHeader(
        code_set=code_set,
        protocol_identifier=protocol_identifier,
        designator_type=designator_type,
        association=association,
        piv=piv,
        designator_length=designator_length,
    )


def parse_designator(designator: memoryview, dhead: DesignatorHeader) -> Designator:
    naa_type = naa_format = None
    if designator.nbytes < 8:
        parsed: str = designator.hex().upper()
    elif dhead.designator_type == "NAA":
        parsed: str = designator.hex().upper()
        naa_type: int = (designator[0] & 0xF0) >> 4
        naa_format: str = NAAFormats.get(naa_type, "Reserved")
    elif dhead.code_set == "ASCII":
        parsed: str = bytes(designator).decode("ascii", errors="replace").strip()
    elif dhead.code_set == "UTF8":
        parsed: str = bytes(designator).decode("utf-8", errors="replace").strip("\x00")
    else:
        parsed: str = designator.hex().upper()

    return Designator(
        designator_header=dhead,
        naa_type=naa_type,
        naa_format=naa_format,
        parsed=parsed,
    )


def parse_it(file_path: str) -> Pg83:
    header: NoneType = None
    designators: list = list()
    page_code: int = 0x83
    with open(file_path, "rb") as f:
        data: memoryview = memoryview(f.read())
        header: HeaderInfo = validate_and_parse_header(data, page_code)

        descriptors: memoryview = data[header.header_length :]
        offset: int = 0
        while offset < header.page_length:
            if offset + 4 > descriptors.nbytes:
                raise DataLengthError("Not enough data for designator header.")

            designator_header: DesignatorHeader = parse_designator_header(
                descriptors[offset : offset + 4]
            )
            if designator_header.designator_length > descriptors.nbytes:
                raise DataLengthError("Not enough data for designator.")

            designator_offset: int = offset + 4
            designator_end: int = (
                designator_offset + designator_header.designator_length
            )

            designators.append(
                parse_designator(
                    descriptors[designator_offset:designator_end],
                    designator_header,
                )
            )
            offset: int = designator_end

    return Pg83(header=header, designators=tuple(designators))
