from dataclasses import dataclass
from types import MappingProxyType, NoneType

from .exceptions import DataLengthError, FileTooShort, MismatchHeaderType

PeripheralDeviceType: MappingProxyType = MappingProxyType(
    {
        0: "DIRECT_ACCESS_BLOCK_DEVICE",
        1: "SEQUENTIAL_ACCESS_DEVICE",
        2: "PRINTER_DEVICE",
        3: "PROCESSOR_DEVICE",
        4: "WRITE_ONCE_DEVICE",
        5: "CD_DVD_DEVICE",
        6: "SCANNER_DEVICE",
        7: "OPTICAL_MEMORY_DEVICE",
        8: "MEDIMUM_CHANGER_DEVICE",
        9: "COMMUNICATIONS_DEVICE",
        10: "OBSOLETE",
        11: "OBSOLETE",
        12: "STORAGE_ARRAY_CONTROLLER_DEVICE",
        13: "ENCLOSURE_SERVICES_DEVICE",
        14: "SIMPLIFIED_DIRECT_ACCESS_DEVICE",
        15: "OPTICAL_CARD_READER_WRITER_DEVICE",
        16: "BRIDGE_CONTROLLER_COMMANDS",
        17: "OBJECT_BASED_STORAG_DEVICE",
        18: "AUTOMATION_DRIVE_INTERFACE",
        19: "RESERVED",
        20: "RESERVED",
        21: "RESERVED",
        22: "RESERVED",
        23: "RESERVED",
        24: "RESERVED",
        25: "RESERVED",
        26: "RESERVED",
        27: "RESERVED",
        28: "RESERVED",
        29: "RESERVED",
        30: "WELL_KNOWN_LOGICAL_UNIT",
        31: "UNKNOWN_OR_NO_DEVICE_TYPE",
    }
)


AssociationField: MappingProxyType = MappingProxyType(
    {
        0: "ADDRESSED_LOGICAL_UNIT",
        1: "TARGET_PORT",
        2: "TARGET_DEVICE",
        3: "RESERVED",
    }
)


CodeSetField: MappingProxyType = MappingProxyType(
    {
        0: "RESERVED",
        1: "BINARY",
        2: "ASCII",
        3: "UTF8",
        4: "RESERVED",
        5: "RESERVED",
        6: "RESERVED",
        7: "RESERVED",
        8: "RESERVED",
        9: "RESERVED",
        10: "RESERVED",
        11: "RESERVED",
        12: "RESERVED",
        13: "RESERVED",
        14: "RESERVED",
        15: "RESERVED",
    }
)

ProtocolIdentifierField: MappingProxyType = MappingProxyType(
    {
        0: "FIBRE_CHANNEL",
        1: "OBSOLETE",
        2: "SSA_SCSI3",
        3: "IEEE_1394",
        4: "SCSI_RDMA",
        5: "ISCSI",
        6: "SAS_SERIAL_SCSI_PROTOCOL",
        7: "AUTOMATION_DRIVE_INTERFACE_TRANSPORT_PROTOCOL",
        8: "AT_ATTACHMENT_INTERFACE",
        9: "USB_ATTACHED_SCSI",
        10: "SCSI_OVER_PCIE",
        11: "PCIE_PROTOCOLS",
        12: "RESERVED",
        13: "RESERVED",
        14: "RESERVED",
        15: "NO_SPECIFIC_PROTOCOL",
    }
)

DesignatorTypeField: MappingProxyType = MappingProxyType(
    {
        0: "VENDOR_SPECIFIC",
        1: "T10_VENDOR_ID",
        2: "EUI_64",
        3: "NAA",
        4: "RELATIVE_TARGET_PORT",
        5: "TARGET_PORT_GROUP",
        6: "LOGICAL_UNIT_GROUP",
        7: "MD5_LOGICAL_UNIT",
        8: "SCSI_NAME_STRING",
        9: "PROTOCOL_SPECIFIC_PORT",
        10: "UUID",
    }
)

NAAFormats: MappingProxyType = MappingProxyType(
    {
        0: "IEEE Extended",
        1: "Locally Assigned",
        2: "IEEE Registered",
        3: "IEEE Registered Extended",
    }
)


@dataclass(slots=True, frozen=True, kw_only=True)
class HeaderInfo:
    peripheral_device_type: str
    peripheral_qualifier: int
    page_length: int
    header_length: int


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


@dataclass(slots=True, kw_only=True)
class PageInfo:
    header: HeaderInfo
    designators: tuple[Designator]


def validate_and_parse_header(data: memoryview) -> HeaderInfo:
    header_length: int = 4
    if data.nbytes < header_length:
        raise FileTooShort("File too short for VPD Page 0x83")

    header: memoryview = data[:header_length]
    if header[1] != 0x83:
        raise MismatchHeaderType(
            f"Unexpected page code: {hex(header[1])}, expected 0x83."
        )

    peripheral_qualifier: int = header[0] >> 5
    page_length: int = int.from_bytes(header[2:4], byteorder="big")
    try:
        peripheral_device_type: str = PeripheralDeviceType[header[0] & 0x1F]
    except KeyError:
        peripheral_device_type: str = PeripheralDeviceType[31]

    return HeaderInfo(
        peripheral_device_type=peripheral_device_type,
        peripheral_qualifier=peripheral_qualifier,
        page_length=page_length,
        header_length=header_length,
    )


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


def parse_it(file_path: str) -> PageInfo:
    header = None
    designators = list()
    with open(file_path, "rb") as f:
        data: memoryview = memoryview(f.read())
        header: HeaderInfo = validate_and_parse_header(data)

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

            designator_offset = offset + 4
            designator_end = designator_offset + designator_header.designator_length

            designators.append(
                parse_designator(
                    descriptors[designator_offset:designator_end],
                    designator_header,
                )
            )
            offset = designator_end

    return PageInfo(header=header, designators=tuple(designators))
