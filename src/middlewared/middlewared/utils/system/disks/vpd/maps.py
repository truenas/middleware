from types import MappingProxyType

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
