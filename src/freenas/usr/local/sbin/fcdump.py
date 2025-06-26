#!/usr/bin/env python3
"""
Fibre Channel Diagnostic Tool

This script extracts and displays useful information from Linux systems with
Fibre Channel (FC) host adapters installed. It provides:

1. SFP/SFP+ transceiver information from EEPROM data
2. Fibre Channel host adapter statistics including:
   - Traffic counters (frames, words, FCP requests)
   - Error counters (CRC errors, link failures)
   - FPIN (Fabric Performance Impact Notifications)
   - Exchange and sequence management statistics

The tool reads data from sysfs filesystem paths:
- /sys/class/fc_host/host*/device/sfp (SFP EEPROM data)
- /sys/class/fc_host/host*/statistics/* (FC statistics)

Requires:
- Linux system with FC HBAs
- Python 3.6+
- rich library for formatted output
- Appropriate permissions to read sysfs FC data

Usage:
    python3 fcdump.py [--format {rich,text,json}] [--pretty]

Examples:
    python3 fcdump.py                    # Rich formatted output (default)
    python3 fcdump.py -f text            # Plain text with ASCII tables
    python3 fcdump.py -f json            # JSON output (compact)
    python3 fcdump.py -f json --pretty   # JSON output (pretty-printed)
"""

import os
import glob
import json
import argparse
from typing import Dict, List, Any
from rich.console import Console
from rich.table import Table
from rich import box

console = Console()

# Global output configuration (deprecated - will be removed)
output_format = "rich"  # Default format
json_pretty = False     # Pretty print JSON

# SFP EEPROM field offsets and sizes (per SFF-8472 Rev 12.4)
# Serial ID Data memory map at A0h (Table 4-1: "Serial ID Data")
SFP_EEPROM_SIZE = 256  # Standard SFP EEPROM size in bytes
SFP_MIN_DATA_SIZE = 88  # Minimum data size for basic fields through date code
SFP_VENDOR_NAME_OFFSET = 20    # Bytes 20-35: Vendor name (ASCII)
SFP_VENDOR_NAME_SIZE = 16
SFP_VENDOR_OUI_OFFSET = 37     # Bytes 37-39: Vendor IEEE OUI
SFP_PART_NUMBER_OFFSET = 40    # Bytes 40-55: Vendor part number (ASCII)
SFP_PART_NUMBER_SIZE = 16
SFP_SERIAL_NUMBER_OFFSET = 68  # Bytes 68-83: Vendor serial number (ASCII)
SFP_SERIAL_NUMBER_SIZE = 16
SFP_DATE_CODE_OFFSET = 84      # Bytes 84-91: Date code (YYMMDD format)
SFP_DATE_CODE_SIZE = 8
SFP_CONNECTOR_TYPE_OFFSET = 2  # Byte 2: Connector type
SFP_PHYSICAL_DEVICE_OFFSET = 0  # Byte 0: Physical device identifier
# (SFF-8024 Table 4-1)
SFP_COMPLIANCE_CODES_OFFSET = 3  # Bytes 3-10: Transceiver compliance codes
# (SFF-8472 Table 5-3)
SFP_COMPLIANCE_CODES_SIZE = 8  # 8 bytes for main compliance codes
SFP_COMPLIANCE_CODES_END = (SFP_COMPLIANCE_CODES_OFFSET +
                            SFP_COMPLIANCE_CODES_SIZE)  # 11
SFP_EXTENDED_COMPLIANCE_OFFSET = 36  # Byte 36: Extended compliance codes
# (SFF-8472 Table 5-3)
SFP_EXTENDED_COMPLIANCE2_OFFSET = 62  # Byte 62: Additional extended
# compliance codes (SFF-8472 Table 5-3)
SFP_ENCODING_OFFSET = 11       # Byte 11: Encoding
SFP_BR_NOMINAL_OFFSET = 12     # Byte 12: Bit rate, nominal (x100 MBd)
SFP_LENGTH_SMF_OFFSET = 14     # Byte 14: Link length SMF (km)
SFP_LENGTH_SMF_100M_OFFSET = 15  # Byte 15: Link length SMF (100m units)
SFP_LENGTH_OM2_OFFSET = 16     # Byte 16: Link length 50μm OM2 (10m units)
SFP_LENGTH_OM1_OFFSET = 17     # Byte 17: Link length 62.5μm OM1 (10m units)
SFP_LENGTH_OM4_OFFSET = 18     # Byte 18: Link length 50μm OM4 (10m units)
SFP_LENGTH_OM3_OFFSET = 19     # Byte 19: Link length 50μm OM3 (10m units)

# Fibre Channel frame calculation constants (per FC-FS-3 Rev 1.90)
FC_MAX_PAYLOAD_BYTES = 2112    # Maximum FC frame payload (FC-FS-3 Table 8)
FC_HEADER_TRAILER_BYTES = 36   # FC header (24) + CRC (4) + trailer (8)
FC_FRAME_SIZE_BYTES = FC_MAX_PAYLOAD_BYTES + FC_HEADER_TRAILER_BYTES  # 2148
FC_MIN_FRAME_BYTES = 36        # Minimum frame size (header + trailer only)
FC_BITS_PER_BYTE = 8
GBPS_CONVERSION = 1e9          # Convert bits/sec to Gbps

# Special values
FC_STAT_UNAVAILABLE = 0xFFFFFFFFFFFFFFFF  # Indicates unavailable statistic

# Linux sysfs paths (per Documentation/ABI/stable/sysfs-class-fc)
FC_HOST_SFP_PATH_PATTERN = '/sys/class/fc_host/host*/device/sfp'
FC_HOST_STATS_PATH_PATTERN = '/sys/class/fc_host/host*/statistics'

# Files to skip during statistics collection (write-only or non-readable)
FC_STATS_SKIP_FILES = {'reset_statistics'}  # Write-only file for resetting

# SFP EEPROM field decode tables (per SFF-8024 Rev 4.9 reference code tables)
# These tables decode raw values from EEPROM into human-readable text

# Connector Types (SFF-8024 Table 4-3)
SFP_CONNECTOR_TYPES = {
    0x00: "Unknown",
    0x01: "SC (Subscriber Connector)",
    0x02: "Fibre Channel Style 1 copper connector",
    0x03: "Fibre Channel Style 2 copper connector",
    0x04: "BNC/TNC (Bayonet/Threaded Neill-Concelman)",
    0x05: "Fibre Channel coax headers",
    0x06: "Fiber Jack",
    0x07: "LC (Lucent Connector)",
    0x08: "MT-RJ (Mechanical Transfer - Registered Jack)",
    0x09: "MU (Multiple Optical)",
    0x0A: "SG",
    0x0B: "Optical Pigtail",
    0x0C: "MPO 1x12 (Multifiber Push On)",
    0x0D: "MPO 2x16",
    0x20: "HSSDC II (High Speed Serial Data Connector)",
    0x21: "Copper pigtail",
    0x22: "RJ45 (Registered Jack)",
    0x23: "No separable connector",
    0x24: "MXC 2x16",
    0x25: "CS optical connector",
    0x26: "Mini CS optical connector",
    0x27: "MPO 2x12",
    0x28: "MPO 1x16",
}

# Physical Device Types (SFF-8024 Table 4-1) - Byte 0 identifier values
SFP_PHYSICAL_DEVICE_TYPES = {
    0x00: "Unknown",
    0x01: "GBIC",
    0x02: "Module/connector soldered to motherboard",
    0x03: "SFP/SFP+/SFP28",
    0x04: "300 pin XBI",
    0x05: "XENPAK",
    0x06: "XFP",
    0x07: "XFF",
    0x08: "XFP-E",
    0x09: "XPAK",
    0x0A: "X2",
    0x0B: "DWDM-SFP/SFP+",
    0x0C: "QSFP",
    0x0D: "QSFP+",
    0x11: "CXP or later",
    0x12: "Shielded Mini Multilane HD 4X",
    0x13: "Shielded Mini Multilane HD 8X",
    0x18: "QSFP28 or later",
    0x19: "CXP2 (aka CXP28) or later",
    0x1A: "CDFP (Style 1/Style2)",
    0x1B: "Shielded Mini Multilane HD 4X Fanout Cable",
    0x1C: "Shielded Mini Multilane HD 8X Fanout Cable",
    0x1D: "CDFP (Style 3)",
    0x1E: "microQSFP",
    0x1F: "QSFP-DD Double Density 8X",
    0x20: "OSFP",
    0x21: "SFP-DD Double Density 2X",
    0x22: "DSFP Dual SFP",
    0x23: "x4 MiniLink/OcuLink",
    0x24: "x8 MiniLink",
    0x25: "QSFP+ or later with CMIS",
}

# Encoding Types (SFF-8024 Table 4-2 Rev 4.9)
# Per SFF-8024 specification: for modules supporting multiple encoding types,
# the primary product application dictates the value chosen. In case of
# conflict
# between modulation and coding, the code for modulation should be used.
SFP_ENCODING_TYPES = {
    0x00: "Unspecified",
    0x01: "8B/10B",
    0x02: "4B/5B",
    0x03: "NRZ (Non-Return-to-Zero)",
    0x04: "Manchester",
    0x05: "SONET Scrambled",
    0x06: "64B/66B",
    0x07: "256B/257B (transcoded FEC-enabled data)",
    0x08: "PAM4",
    # Values 0x09-0xFF are reserved per SFF-8024 Table 4-2
}

# SFP Compliance Codes bit definitions (SFF-8472 Table 5-3)
# Complete bit mappings from official SFF-8472 Rev 12.4 specification
SFP_COMPLIANCE_10G_ETHERNET = {
    # Byte 3: 10G Ethernet Compliance Codes (bits 7-4)
    7: "10GBASE-ER",
    6: "10GBASE-LRM",
    5: "10GBASE-LR",
    4: "10GBASE-SR",
}

SFP_COMPLIANCE_INFINIBAND = {
    # Byte 3: Infiniband Compliance Codes (bits 3-0)
    3: "1X SX",
    2: "1X LX",
    1: "1X Copper Active",
    0: "1X Copper Passive",
}

SFP_COMPLIANCE_ESCON = {
    # Byte 4: ESCON Compliance Codes (bits 7-6)
    7: "ESCON MMF, 1310nm LED",
    6: "ESCON SMF, 1310nm Laser",
}

SFP_COMPLIANCE_SONET_BYTE4 = {
    # Byte 4: SONET Compliance Codes (bits 5-0)
    5: "OC-192, short reach",
    4: "SONET reach specifier bit 1",
    3: "SONET reach specifier bit 2",
    2: "OC-48, long reach",
    1: "OC-48, intermediate reach",
    0: "OC-48, short reach",
}

SFP_COMPLIANCE_SONET_BYTE5 = {
    # Byte 5: SONET Compliance Codes (bits 7-0)
    7: "Reserved",
    6: "OC-12, single mode, long reach",
    5: "OC-12, single mode, inter. reach",
    4: "OC-12, short reach",
    3: "Reserved",
    2: "OC-3, single mode, long reach",
    1: "OC-3, single mode, inter. reach",
    0: "OC-3, short reach",
}

SFP_COMPLIANCE_ETHERNET = {
    # Byte 6: Ethernet Compliance Codes
    7: "BASE-PX",
    6: "BASE-BX10",
    5: "100BASE-FX",
    4: "100BASE-LX/LX10",
    3: "1000BASE-T",
    2: "1000BASE-CX",
    1: "1000BASE-LX",
    0: "1000BASE-SX",
}

SFP_COMPLIANCE_FIBRE_CHANNEL_LENGTH = {
    # Byte 7: Fibre Channel Link Length
    7: "very long distance (V)",
    6: "short distance (S)",
    5: "intermediate distance (I)",
    4: "long distance (L)",
    3: "medium distance (M)",
    # Bits 0-2 reserved
}

SFP_COMPLIANCE_FIBRE_CHANNEL_TECH_BYTE7 = {
    # Byte 7: Fibre Channel Transmitter Technology (bits 2-0)
    2: "Shortwave laser, linear Rx (SA)",
    1: "Longwave laser (LC)",
    0: "Electrical inter-enclosure (EL)",
}

SFP_COMPLIANCE_FIBRE_CHANNEL_TECH_BYTE8 = {
    # Byte 8: Fibre Channel Transmitter Technology (bits 7-4)
    7: "Electrical intra-enclosure (EL)",
    6: "Shortwave laser w/o OFC (SN)",
    5: "Shortwave laser with OFC (SL)",
    4: "Longwave laser (LL)",
}

SFP_COMPLIANCE_CABLE_TECHNOLOGY = {
    # Byte 8: SFP+ Cable Technology (bits 3-2)
    3: "Active Cable",
    2: "Passive Cable",
    # Bits 1-0 reserved
}

SFP_COMPLIANCE_FIBRE_CHANNEL_MEDIA = {
    # Byte 9: Fibre Channel Transmission Media
    7: "Twin Axial Pair (TW)",
    6: "Twisted Pair (TP)",
    5: "Miniature Coax (MI)",
    4: "Video Coax (TV)",
    3: "Multimode, 62.5um (M6)",
    2: "Multimode, 50um (M5, M5E)",
    1: "Reserved",
    0: "Single Mode (SM)",
}

SFP_COMPLIANCE_FIBRE_CHANNEL_SPEED = {
    # Byte 10: Fibre Channel Speed
    7: "1200 MBytes/sec",
    6: "800 MBytes/sec",
    5: "1600 MBytes/sec",
    4: "400 MBytes/sec",
    3: "3200 MBytes/sec",
    2: "200 MBytes/sec",
    1: "See byte 62 'Fibre Channel Speed 2'",
    0: "100 MBytes/sec",
}

# Extended Compliance Codes (SFF-8472 Table 5-3, Byte 36 ->
# SFF-8024 Table 4-4)
# Per SFF-8472 spec, byte 36 refers to SFF-8024 Table 4-4 for extended
# compliance codes
SFP_EXTENDED_COMPLIANCE_CODES = {
    # Basic codes
    0x00: "Unspecified",

    # 100G/25G Ethernet (SFF-8024 Rev 4.9+)
    0x01: "100G AOC or 25GAUI C2M AOC",
    0x02: "100GBASE-SR4 or 25GBASE-SR",
    0x03: "100GBASE-LR4 or 25GBASE-LR",
    0x04: "100GBASE-ER4 or 25GBASE-ER",
    0x05: "100GBASE-SR10",
    0x06: "100G CWDM4",
    0x07: "100G PSM4 Parallel SMF",
    0x08: "100G ACC or 25GAUI C2M ACC",
    0x09: "100GBASE-CR4",
    0x0A: "Reserved",
    0x0B: "100GBASE-CR4 or 25GBASE-CR CA-L",
    0x0C: "25GBASE-CR CA-S",
    0x0D: "25GBASE-CR CA-N",
    0x0E: "Reserved",
    0x0F: "Reserved",

    # 40G Ethernet
    0x10: "40GBASE-ER4",
    0x11: "4x10GBASE-SR",
    0x12: "40G PSM4 Parallel SMF",
    0x13: "G959.1 profile P1I1-2D1",
    0x14: "G959.1 profile P1S1-2D2",
    0x15: "G959.1 profile P1L1-2D2",
    0x16: "10GBASE-T with SFI electrical interface",
    0x17: "100G CLR4",
    0x18: "100G AOC or 25GAUI C2M AOC",
    0x19: "100G ACC or 25GAUI C2M ACC",
    0x1A: "100GE-DWDM2",
    0x1B: "100G 1550nm WDM",
    0x1C: "10GBASE-T Short Reach",
    0x1D: "5GBASE-T",
    0x1E: "2.5GBASE-T",
    0x1F: "40G SWDM4",

    # 100G Additional codes (0x20-0x3F)
    0x20: "100GBASE-DR",
    0x21: "100G-FR or 100GBASE-FR1",
    0x22: "100G-LR or 100GBASE-LR1",
    0x23: "Reserved",
    0x24: "Reserved",
    0x25: "Reserved",
    0x26: "Reserved",
    0x27: "Reserved",
    0x28: "Reserved",
    0x29: "Reserved",
    0x2A: "Reserved",
    0x2B: "Reserved",
    0x2C: "Reserved",
    0x2D: "Reserved",
    0x2E: "Reserved",
    0x2F: "Reserved",

    # 200G/50G codes (0x40-0x4F)
    0x40: "50GBASE-CR, 100GBASE-CR2, or 200GBASE-CR4",
    0x41: "50GBASE-SR, 100GBASE-SR2, or 200GBASE-SR4",
    0x42: "50GBASE-FR or 200GBASE-DR4",
    0x43: "200GBASE-FR4",
    0x44: "200G 1550 nm PSM4",
    0x45: "50GBASE-LR",
    0x46: "200GBASE-LR4",
    0x47: "400GBASE-DR4 (802.3, Clause 124), 400GAUI-4 C2M " +
          "(Annex 120G)",
    0x48: "400GBASE-FR4 (802.3, Clause 151)",
    0x49: "400GBASE-LR4-6 (802.3, Clause 151)",
    0x4A: "50GBASE-ER (IEEE 802.3, Clause 139)",
    0x4B: "400G-LR4-10",
    0x4C: "400GBASE-ZR (P802.3cw, Clause 156)",
    0x4D: "Reserved",
    0x4E: "Reserved",
    0x4F: "Reserved",

    # Reserved codes 0x4D-0x7E per SFF-8024 Rev 4.12
    # (keeping existing Fibre Channel codes for backward compatibility)

    # Fibre Channel codes (0x50-0x5F) - NOTE: These were removed in
    # SFF-8024 Rev 4.12
    # but preserved here for backward compatibility. New codes are at
    # 0x7F-0x81
    0x50: "64GFC EA",
    0x51: "64GFC SW",
    0x52: "64GFC LW",
    0x53: "128GFC EA",
    0x54: "128GFC SW",
    0x55: "128GFC LW",
    0x56: "Reserved",
    0x57: "Reserved",
    0x58: "Reserved",
    0x59: "Reserved",
    0x5A: "Reserved",
    0x5B: "Reserved",
    0x5C: "Reserved",
    0x5D: "Reserved",
    0x5E: "Reserved",
    0x5F: "Reserved",

    # Values 0x60-0x7E are reserved per SFF-8024 Rev 4.12

    # Official Fibre Channel codes from SFF-8024 Rev 4.12
    0x7F: "256GFC-SW4 (FC-PI-7P)",
    0x80: "64GFC (FC-PI-7)",
    0x81: "128GFC (FC-PI-8)",

    # Values 0x82-0xFF are reserved for future use
}

# Additional Extended Compliance Codes (SFF-8472 Table 5-3, Byte 62)
SFP_EXTENDED_COMPLIANCE2_CODES = {
    0x00: "Unspecified",
    # Extended compliance codes for newer standards would be added here
}


def decode_compliance_codes(data: bytes) -> List[str]:
    """
    Decode SFP compliance codes from all relevant bytes (SFF-8472 Table 5-3).

    Decodes compliance codes from:
    - Bytes 3-10: Main transceiver compliance codes
    - Byte 36: Extended compliance codes
    - Byte 62: Additional extended compliance codes

    Args:
        data: Binary EEPROM data

    Returns:
        List of supported protocols/capabilities
    """
    capabilities = []

    # Check if we have enough data for basic compliance codes (bytes 3-10)
    if len(data) < SFP_COMPLIANCE_CODES_END:
        return ["Insufficient data for compliance codes"]

    # Bytes 3-10: Main compliance codes
    compliance_data = data[SFP_COMPLIANCE_CODES_OFFSET:
                           SFP_COMPLIANCE_CODES_END]

    # Byte 3: 10G Ethernet Compliance Codes (bits 7-4) and Infiniband
    # (bits 3-0)
    if len(compliance_data) > 0:
        byte3 = compliance_data[0]
        # Check 10G Ethernet compliance codes (bits 7-4)
        for bit, description in SFP_COMPLIANCE_10G_ETHERNET.items():
            if byte3 & (1 << bit):
                capabilities.append(f"10GbE: {description}")
        # Check Infiniband compliance codes (bits 3-0)
        for bit, description in SFP_COMPLIANCE_INFINIBAND.items():
            if byte3 & (1 << bit):
                capabilities.append(f"Infiniband: {description}")

    # Byte 4: ESCON Compliance Codes (bits 7-6) and SONET (bits 5-0)
    if len(compliance_data) > 1:
        byte4 = compliance_data[1]
        # ESCON compliance codes (bits 7-6)
        for bit, description in SFP_COMPLIANCE_ESCON.items():
            if byte4 & (1 << bit):
                capabilities.append(f"ESCON: {description}")
        # SONET compliance codes (bits 5-0)
        for bit, description in SFP_COMPLIANCE_SONET_BYTE4.items():
            if byte4 & (1 << bit):
                capabilities.append(f"SONET: {description}")

    # Byte 5: SONET Compliance Codes (bits 7-0)
    if len(compliance_data) > 2:
        byte5 = compliance_data[2]
        for bit, description in SFP_COMPLIANCE_SONET_BYTE5.items():
            if byte5 & (1 << bit):
                capabilities.append(f"SONET: {description}")

    # Byte 6: Ethernet Compliance Codes
    if len(compliance_data) > 3:
        byte6 = compliance_data[3]
        for bit, description in SFP_COMPLIANCE_ETHERNET.items():
            if byte6 & (1 << bit):
                capabilities.append(f"Ethernet: {description}")

    # Byte 7: Fibre Channel Link Length (bits 7-3) and FC Technology (bits 2-0)
    if len(compliance_data) > 4:
        byte7 = compliance_data[4]
        # FC Link Length (bits 7-3)
        for bit, description in SFP_COMPLIANCE_FIBRE_CHANNEL_LENGTH.items():
            if byte7 & (1 << bit):
                capabilities.append(f"FC Length: {description}")
        # FC Transmitter Technology (bits 2-0)
        for bit, description in \
                SFP_COMPLIANCE_FIBRE_CHANNEL_TECH_BYTE7.items():
            if byte7 & (1 << bit):
                capabilities.append(f"FC Tech: {description}")

    # Byte 8: FC Transmitter Technology (bits 7-4) and SFP+ Cable
    # Technology (bits 3-2)
    if len(compliance_data) > 5:
        byte8 = compliance_data[5]
        # FC Transmitter Technology (bits 7-4)
        for bit, description in \
                SFP_COMPLIANCE_FIBRE_CHANNEL_TECH_BYTE8.items():
            if byte8 & (1 << bit):
                capabilities.append(f"FC Tech: {description}")
        # SFP+ Cable Technology (bits 3-2)
        for bit, description in SFP_COMPLIANCE_CABLE_TECHNOLOGY.items():
            if byte8 & (1 << bit):
                capabilities.append(f"Cable: {description}")

    # Byte 9: Fibre Channel Transmission Media
    if len(compliance_data) > 6:
        byte9 = compliance_data[6]
        for bit, description in SFP_COMPLIANCE_FIBRE_CHANNEL_MEDIA.items():
            if byte9 & (1 << bit):
                capabilities.append(f"FC Media: {description}")

    # Byte 10: Fibre Channel Speed
    if len(compliance_data) > 7:
        byte10 = compliance_data[7]
        for bit, description in SFP_COMPLIANCE_FIBRE_CHANNEL_SPEED.items():
            if byte10 & (1 << bit):
                capabilities.append(f"FC Speed: {description}")

    # Byte 36: Extended compliance codes
    if len(data) > SFP_EXTENDED_COMPLIANCE_OFFSET:
        byte36 = data[SFP_EXTENDED_COMPLIANCE_OFFSET]
        if byte36 != 0:
            ext_desc = SFP_EXTENDED_COMPLIANCE_CODES.get(
                byte36, f"Unknown (0x{byte36:02X})")
            capabilities.append(f"Extended: {ext_desc}")

    # Byte 62: Additional extended compliance codes
    if len(data) > SFP_EXTENDED_COMPLIANCE2_OFFSET:
        byte62 = data[SFP_EXTENDED_COMPLIANCE2_OFFSET]
        if byte62 != 0:
            ext2_desc = SFP_EXTENDED_COMPLIANCE2_CODES.get(
                byte62, f"Unknown (0x{byte62:02X})")
            capabilities.append(f"Extended 2: {ext2_desc}")

    # Add basic capability detection for common protocols
    has_main_codes = any(compliance_data)
    has_ext_codes = (len(data) > SFP_EXTENDED_COMPLIANCE_OFFSET and
                     data[SFP_EXTENDED_COMPLIANCE_OFFSET] != 0)
    has_ext2_codes = (len(data) > SFP_EXTENDED_COMPLIANCE2_OFFSET and
                      data[SFP_EXTENDED_COMPLIANCE2_OFFSET] != 0)
    if has_main_codes or has_ext_codes or has_ext2_codes:
        if not capabilities:
            capabilities.append("Proprietary or extended capabilities")
    else:
        capabilities.append("No compliance codes set")

    return capabilities


def extract_host_and_filename(path: str) -> tuple[str, str]:
    """
    Extract host name and filename from SFP path.

    Args:
        path: Full path like '/sys/class/fc_host/host0/device/sfp'

    Returns:
        Tuple of (host_name, filename)
    """
    # Extract filename
    filename = path.split('/')[-1] if '/' in path else path

    # Extract host name - look for pattern like 'host0', 'host1', etc.
    path_parts = path.split('/')
    host_name = "unknown"
    for part in path_parts:
        if part.startswith('host') and part[4:].isdigit():
            host_name = part
            break

    return host_name, filename


def parse_protocol_support(capabilities: list) -> Dict[str, Any]:
    """
    Parse protocol support capabilities into structured data.

    Args:
        capabilities: List of protocol capability strings

    Returns:
        Dictionary with structured protocol support data
    """
    protocol_dict = {}
    raw_capabilities = capabilities[:]

    for capability in capabilities:
        if ":" in capability:
            protocol_type, description = capability.split(":", 1)
            protocol_type = protocol_type.strip()
            description = description.strip()
            if protocol_type not in protocol_dict:
                protocol_dict[protocol_type] = []
            protocol_dict[protocol_type].append(description)
        else:
            # Handle capabilities without colons
            if "General" not in protocol_dict:
                protocol_dict["General"] = []
            protocol_dict["General"].append(capability)

    return {
        "structured": protocol_dict,
        "raw_list": raw_capabilities
    }


# FC statistics grouping (per FC-LS-3 Rev 1.80 and Linux fc_host documentation)
# FPIN = Fabric Performance Impact Notification (FC-LS-3 Section 25.6)
# DN = Delivery Notification, CN = Congestion Notification, LI = Link Integrity
GROUPS = {
    "General Counters": [
        "seconds_since_last_reset", "lip_count", "nos_count",
        "loss_of_signal_count", "loss_of_sync_count"
    ],
    "Traffic Stats": [
        "rx_frames", "rx_words", "tx_frames", "tx_words",
        "fcp_input_requests", "fcp_input_megabytes",
        "fcp_output_requests", "fcp_output_megabytes",
        "fcp_control_requests"
    ],
    "Error Counters": [
        "error_frames", "invalid_crc_count", "invalid_tx_word_count",
        "dumped_frames", "link_failure_count"
    ],
    "Exchange/XID Issues": [
        "fc_no_free_exch", "fc_no_free_exch_xid", "fc_xid_not_found",
        "fc_xid_busy", "fc_seq_not_found", "fc_non_bls_resp"
    ],
    "FCP Specific Failures": [
        "fcp_packet_alloc_failures", "fcp_frame_alloc_failures",
        "fcp_packet_aborts"
    ],
    "FPIN - DN (Delivery Notification)": [
        "fpin_dn", "fpin_dn_device_specific", "fpin_dn_timeout",
        "fpin_dn_unable_to_route", "fpin_dn_unknown"
    ],
    "FPIN - CN (Congestion Notification)": [
        "fpin_cn", "fpin_cn_clear", "fpin_cn_credit_stall",
        "fpin_cn_oversubscription", "fpin_cn_device_specific",
        "fpin_cn_lost_credit"
    ],
    "FPIN - LI (Link Integrity)": [
        "fpin_li", "fpin_li_device_specific", "fpin_li_invalid_crc_count",
        "fpin_li_invalid_tx_word_count", "fpin_li_link_failure_count",
        "fpin_li_loss_of_signals_count", "fpin_li_loss_of_sync_count",
        "fpin_li_prim_seq_err_count", "fpin_li_failure_unknown"
    ],
    "Signals & Alarms": ["cn_sig_alarm", "cn_sig_warn"]
}


def parse_arguments() -> argparse.Namespace:
    """
    Parse command line arguments for output format selection.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Extract Fibre Channel diagnostic information",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Output formats:
  rich     - Rich formatted tables with colors (default)
  text     - Plain text tables with ASCII box drawing
  json     - JSON format output
        """
    )
    parser.add_argument(
        '--format', '-f',
        choices=['rich', 'text', 'json'],
        default='rich',
        help='Output format (default: rich)'
    )
    parser.add_argument(
        '--pretty', '-p',
        action='store_true',
        help='Pretty print JSON output (only applies to JSON format)'
    )
    return parser.parse_args()


def draw_text_table(title: str, headers: List[str],
                    rows: List[List[str]]) -> str:
    """
    Draw a plain text table with ASCII box drawing characters.
    Supports multiline cell content.

    Args:
        title: Table title
        headers: Column headers
        rows: Table rows (each row is a list of strings, may contain newlines)

    Returns:
        Formatted ASCII table as string
    """
    if not rows:
        return ""

    # Split each cell by newlines and track maximum lines per row
    split_rows = []
    for row in rows:
        split_row = [str(cell).split('\n') for cell in row]
        split_rows.append(split_row)

    # Calculate column widths considering all lines in multiline cells
    col_widths = [len(h) for h in headers]
    for split_row in split_rows:
        for col_idx, cell_lines in enumerate(split_row):
            if col_idx < len(col_widths):
                for line in cell_lines:
                    col_widths[col_idx] = max(col_widths[col_idx], len(line))

    # Calculate actual table width
    num_separators = len(col_widths) - 1
    separators_width = num_separators * 3
    content_width = sum(col_widths) + separators_width + 4

    # Ensure title fits
    title_width = len(title)
    min_title_width = title_width + 2

    if min_title_width > content_width:
        extra_space = min_title_width - content_width
        col_widths[0] += extra_space
        content_width = min_title_width

    total_width = content_width

    # Build table
    lines = []

    # Top border
    border_line = "+" + "-" * (total_width - 2) + "+"
    lines.append(border_line)

    # Title line
    title_padding = (total_width - 2 - len(title)) // 2
    title_line = ("|" + " " * title_padding + title +
                  " " * (total_width - 2 - title_padding - len(title)) + "|")
    lines.append(title_line)

    # Header separator
    lines.append(border_line)

    # Headers
    header_line = ("| " +
                   " | ".join(h.ljust(w) for h, w in zip(headers,
                                                         col_widths)) +
                   " |")
    lines.append(header_line)

    # Header bottom border
    lines.append(border_line)

    # Data rows with multiline support
    for split_row in split_rows:
        # Find the maximum number of lines in this row
        max_lines = max(len(cell_lines) for cell_lines in split_row)

        # Render each line of this row
        for line_idx in range(max_lines):
            row_parts = []
            for col_idx, cell_lines in enumerate(split_row):
                if col_idx < len(col_widths):
                    # Get line text or empty if this cell has fewer lines
                    line_text = (cell_lines[line_idx]
                                 if line_idx < len(cell_lines) else "")
                    row_parts.append(line_text.ljust(col_widths[col_idx]))
                else:
                    row_parts.append("")

            row_line = "| " + " | ".join(row_parts) + " |"
            lines.append(row_line)

    # Bottom border
    lines.append(border_line)

    return "\n".join(lines)


def print_text_output(text: str) -> None:
    """Print text output to stdout."""
    print(text)


def decode_sfp_field(value: int,
                     decode_table: Dict[int, str]) -> Dict[str, Any]:
    """
    Decode SFP EEPROM field value using lookup table.

    Args:
        value: Raw integer value from EEPROM
        decode_table: Dictionary mapping values to descriptions

    Returns:
        Dictionary with 'value' and 'text' keys for JSON output,
        or formatted string for text/rich output
    """
    # Special handling for SFF-8024 Table 4-2 encoding types reserved values
    if decode_table is SFP_ENCODING_TYPES and 0x09 <= value <= 0xFF:
        text_desc = f"Reserved (0x{value:02X})"
    else:
        text_desc = decode_table.get(value, f"Unknown (0x{value:02X})")
    return {"value": value, "text": text_desc}


def format_decoded_field(decoded: Dict[str, Any],
                         for_json: bool = False) -> Any:
    """
    Format decoded field for different output types.

    Args:
        decoded: Dictionary with 'value' and 'text' keys
        for_json: True if formatting for JSON output

    Returns:
        Dictionary for JSON, formatted string for text/rich
    """
    if for_json:
        return decoded
    else:
        return f"{decoded['value']} ({decoded['text']})"


def decode_str(data: bytes, start: int, length: int) -> str:
    """
    Decode ASCII string from binary data with bounds checking.

    Args:
        data: Binary data buffer
        start: Starting byte offset
        length: Number of bytes to decode

    Returns:
        Decoded ASCII string, stripped of whitespace
    """
    if len(data) < start + length:
        return ""
    return data[start:start + length].decode('ascii', errors='ignore').strip()


def collect_sfp_eeprom_data(path: str) -> Dict[str, Any]:
    """
    Collect SFP/SFP+ transceiver EEPROM information from sysfs.

    Reads SFP EEPROM data according to SFF-8472 specification and extracts
    vendor information, part numbers, and transceiver characteristics.

    Args:
        path: Path to SFP EEPROM file in sysfs

    Returns:
        Dictionary containing parsed SFP data or error information
    """
    result = {
        "path": path,
        "success": False,
        "error": None,
        "fields": {}
    }

    try:
        with open(path, "rb") as f:
            data = f.read(SFP_EEPROM_SIZE)
    except Exception as e:
        result["error"] = f"Error reading {path}: {e}"
        return result

    if len(data) < SFP_MIN_DATA_SIZE:
        result["error"] = (f"EEPROM data too short "
                           f"({len(data)} bytes) in {path}")
        return result

    # Basic string fields
    result["fields"]["Vendor Name"] = decode_str(
        data, SFP_VENDOR_NAME_OFFSET, SFP_VENDOR_NAME_SIZE)
    result["fields"]["Vendor OUI"] = (
        f"{data[SFP_VENDOR_OUI_OFFSET]:02X}-"
        f"{data[SFP_VENDOR_OUI_OFFSET+1]:02X}-"
        f"{data[SFP_VENDOR_OUI_OFFSET+2]:02X}"
        if len(data) >= SFP_VENDOR_OUI_OFFSET + 3
        else "Not available")
    result["fields"]["Part Number"] = decode_str(
        data, SFP_PART_NUMBER_OFFSET, SFP_PART_NUMBER_SIZE)
    result["fields"]["Serial Number"] = decode_str(
        data, SFP_SERIAL_NUMBER_OFFSET, SFP_SERIAL_NUMBER_SIZE)
    result["fields"]["Date Code"] = decode_str(
        data, SFP_DATE_CODE_OFFSET, SFP_DATE_CODE_SIZE)

    # Decoded fields with raw and text values
    if len(data) > SFP_CONNECTOR_TYPE_OFFSET:
        result["fields"]["Connector Type"] = decode_sfp_field(
            data[SFP_CONNECTOR_TYPE_OFFSET], SFP_CONNECTOR_TYPES)
    else:
        result["fields"]["Connector Type"] = {"value": 0, "text": "N/A"}

    if len(data) > SFP_PHYSICAL_DEVICE_OFFSET:
        result["fields"]["Physical Device Type"] = decode_sfp_field(
            data[SFP_PHYSICAL_DEVICE_OFFSET], SFP_PHYSICAL_DEVICE_TYPES)
    else:
        result["fields"]["Physical Device Type"] = {"value": 0, "text": "N/A"}

    # Protocol support
    if len(data) >= SFP_COMPLIANCE_CODES_END:
        result["fields"]["Protocol Support"] = parse_protocol_support(
            decode_compliance_codes(data))
    else:
        result["fields"]["Protocol Support"] = {
            "structured": {"General": ["Insufficient data"]},
            "raw_list": ["Insufficient data"]
        }

    # Encoding
    if len(data) > SFP_ENCODING_OFFSET:
        result["fields"]["Encoding"] = decode_sfp_field(
            data[SFP_ENCODING_OFFSET], SFP_ENCODING_TYPES)
    else:
        result["fields"]["Encoding"] = {"value": 0, "text": "N/A"}

    # Numeric fields
    result["fields"]["BR, nominal"] = (
        {"value": data[SFP_BR_NOMINAL_OFFSET], "unit": "x100MBd"}
        if len(data) > SFP_BR_NOMINAL_OFFSET else {"value": 0, "unit": "N/A"})

    # Length fields
    length_fields = [
        ("Length SMF (km)", SFP_LENGTH_SMF_OFFSET, 1, "km"),
        ("Length SMF (100m)", SFP_LENGTH_SMF_100M_OFFSET, 100, "m"),
        ("Length OM2 (m)", SFP_LENGTH_OM2_OFFSET, 10, "m"),
        ("Length OM1 (m)", SFP_LENGTH_OM1_OFFSET, 10, "m"),
        ("Length OM4 (m)", SFP_LENGTH_OM4_OFFSET, 10, "m"),
        ("Length OM3 (m)", SFP_LENGTH_OM3_OFFSET, 10, "m"),
    ]

    for field_name, offset, multiplier, unit in length_fields:
        if len(data) > offset:
            raw_value = data[offset]
            result["fields"][field_name] = {
                "raw_value": raw_value,
                "value": raw_value * multiplier,
                "unit": unit
            }
        else:
            result["fields"][field_name] = {
                "raw_value": 0,
                "value": 0,
                "unit": "N/A"
            }

    result["success"] = True
    return result


def hex_to_dec(value: str) -> str:
    """
    Convert hexadecimal or decimal string to decimal string.

    Handles special case where 0xFFFFFFFFFFFFFFFF indicates unavailable data.

    Args:
        value: String containing hex or decimal number

    Returns:
        Decimal string representation, or "N/A" for invalid/unavailable data
    """
    try:
        num = int(value, 16)
    except ValueError:
        try:
            num = int(value)
        except ValueError:
            return value
    if num == FC_STAT_UNAVAILABLE:
        return "N/A"
    return str(num)


def collect_fc_statistics() -> Dict[str, Dict[str, Any]]:
    """
    Collect Fibre Channel statistics for all FC host adapters.

    Scans /sys/class/fc_host/host*/statistics directories and reads all
    available statistics files. Handles permission errors gracefully.

    Returns:
        Dictionary mapping host names to their statistics data
    """
    result = {}
    hosts = glob.glob(FC_HOST_STATS_PATH_PATTERN)

    for host_stats_dir in hosts:
        host_name = os.path.basename(os.path.dirname(host_stats_dir))
        host_data = {
            "success": False,
            "error": None,
            "stats": {},
            "grouped_stats": {}
        }

        try:
            stat_files = os.listdir(host_stats_dir)
        except PermissionError:
            host_data["error"] = f"Permission denied reading {host_stats_dir}"
            result[host_name] = host_data
            continue

        for stat_file in stat_files:
            # Skip write-only or non-readable files
            if stat_file in FC_STATS_SKIP_FILES:
                continue
            stat_path = os.path.join(host_stats_dir, stat_file)
            try:
                with open(stat_path, 'r') as f:
                    raw = f.read().strip()
                    processed_value = hex_to_dec(raw)
                    host_data["stats"][stat_file] = {
                        "raw": raw,
                        "processed": processed_value
                    }
            except PermissionError:
                host_data["stats"][stat_file] = {
                    "raw": None,
                    "processed": "Permission denied",
                    "error": "Permission denied"
                }
            except Exception as e:
                host_data["stats"][stat_file] = {
                    "raw": None,
                    "processed": f"Error reading: {e}",
                    "error": str(e)
                }

        # Group statistics and calculate bandwidth estimates
        host_data["grouped_stats"] = group_fc_statistics(host_data["stats"])
        host_data["success"] = True
        result[host_name] = host_data

    return result


def group_fc_statistics(stats: Dict[str, Dict[str, Any]]) -> \
        Dict[str, Dict[str, Any]]:
    """
    Group FC statistics by category and calculate bandwidth estimates.

    Args:
        stats: Dictionary of raw statistics

    Returns:
        Dictionary of grouped statistics with bandwidth calculations
    """
    grouped = {}
    matched = set()

    for group, keys in GROUPS.items():
        group_data = {}
        for key in keys:
            if key in stats:
                stat_data = stats[key].copy()
                processed_value = stat_data["processed"]

                # Calculate bandwidth for frame counters
                if (group == "Traffic Stats" and
                        key in ["rx_frames", "tx_frames"] and
                        "seconds_since_last_reset" in stats):
                    seconds_data = stats["seconds_since_last_reset"]
                    seconds_str = seconds_data["processed"]
                    bandwidth = calculate_bandwidth(processed_value,
                                                    seconds_str)
                    stat_data["bandwidth_estimate"] = bandwidth.strip()

                group_data[key] = stat_data
                matched.add(key)

        if group_data:
            grouped[group] = group_data

    # Add ungrouped statistics
    other_keys = sorted(set(stats.keys()) - matched)
    if other_keys:
        grouped["Other"] = {key: stats[key] for key in other_keys}

    return grouped


def calculate_bandwidth(frames_str: str, seconds_str: str) -> str:
    """
    Calculate approximate bandwidth from frame count and time period.

    Uses maximum FC frame size (FC_FRAME_SIZE_BYTES constant) to estimate
    bandwidth. This provides an upper bound since actual frame sizes vary
    from FC_MIN_FRAME_BYTES to FC_FRAME_SIZE_BYTES.

    Args:
        frames_str: String containing frame count
        seconds_str: String containing time period in seconds

    Returns:
        Formatted bandwidth string with Gbps suffix, or empty string if
        invalid
    """
    if frames_str == "N/A" or not frames_str.isdigit():
        return ""
    frames = int(frames_str)
    if seconds_str == "N/A" or not seconds_str.isdigit():
        return ""
    seconds = int(seconds_str)
    if seconds <= 0:
        return ""
    bandwidth_bps = (frames * FC_FRAME_SIZE_BYTES * FC_BITS_PER_BYTE) / seconds
    bandwidth_gbps = bandwidth_bps / GBPS_CONVERSION
    return f" ({bandwidth_gbps:.2f} Gbps)"


def render_sfp_data_json(sfp_data: Dict[str, Any]) -> Dict[str, Any]:
    """Render SFP data for JSON output."""
    if not sfp_data["success"]:
        return {"error": sfp_data["error"]}

    json_fields = {}
    for field_name, field_data in sfp_data["fields"].items():
        if isinstance(field_data, str):
            # Simple string field
            json_fields[field_name] = field_data
        elif isinstance(field_data, dict):
            if "structured" in field_data:
                # Protocol support field
                json_fields[field_name] = field_data["structured"]
            elif "text" in field_data:
                # Decoded field with value and text
                json_fields[field_name] = field_data
            elif "unit" in field_data:
                # Numeric field with unit
                json_fields[field_name] = field_data
            else:
                json_fields[field_name] = field_data

    return json_fields


def render_sfp_data_text(sfp_data: Dict[str, Any]) -> str:
    """Render SFP data for text output."""
    if not sfp_data["success"]:
        return f"ERROR: {sfp_data['error']}"

    # Use shorter title with host info for text format
    path = sfp_data['path']
    host_name, filename = extract_host_and_filename(path)
    title = f"SFP EEPROM: {host_name}/{filename}"
    rows = []

    for field_name, field_data in sfp_data["fields"].items():
        if isinstance(field_data, str):
            # Simple string field
            value = field_data
        elif isinstance(field_data, dict):
            if "structured" in field_data:
                # Protocol support - use multiline format for text tables
                if field_data["raw_list"]:
                    if len(field_data["raw_list"]) == 1:
                        value = field_data["raw_list"][0]
                    else:
                        value = field_data["raw_list"][0]
                        for item in field_data["raw_list"][1:]:
                            value += "\n" + item
                else:
                    value = "None"
            elif "text" in field_data:
                # Decoded field
                value = f"{field_data['value']} ({field_data['text']})"
            elif "unit" in field_data:
                # Numeric field with unit
                if field_data["unit"] == "N/A":
                    value = "N/A"
                else:
                    value = f"{field_data['value']} {field_data['unit']}"
            else:
                value = str(field_data)
        else:
            value = str(field_data)

        rows.append([field_name, value])

    return draw_text_table(title, ["Field", "Value"], rows)


def render_sfp_data_rich(sfp_data: Dict[str, Any]) -> Table:
    """Render SFP data for rich output."""
    path = sfp_data['path']
    host_name, filename = extract_host_and_filename(path)
    title = f"SFP EEPROM: {host_name}/{filename}"
    table = Table(title=title, title_style="bold green", box=box.SQUARE)
    table.add_column("Field", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")

    if not sfp_data["success"]:
        table.add_row("Error", sfp_data["error"])
        return table

    for field_name, field_data in sfp_data["fields"].items():
        if isinstance(field_data, str):
            # Simple string field
            value = field_data
        elif isinstance(field_data, dict):
            if "structured" in field_data:
                # Protocol support - use multiline format for rich
                if field_data["raw_list"]:
                    if len(field_data["raw_list"]) == 1:
                        value = field_data["raw_list"][0]
                    else:
                        value = field_data["raw_list"][0]
                        for item in field_data["raw_list"][1:]:
                            value += "\n" + item
                else:
                    value = "None"
            elif "text" in field_data:
                # Decoded field
                value = f"{field_data['value']} ({field_data['text']})"
            elif "unit" in field_data:
                # Numeric field with unit
                if field_data["unit"] == "N/A":
                    value = "N/A"
                else:
                    value = f"{field_data['value']} {field_data['unit']}"
            else:
                value = str(field_data)
        else:
            value = str(field_data)

        table.add_row(field_name, value)

    return table


def render_fc_stats_json(fc_stats: Dict[str, Dict[str, Any]]) -> \
        Dict[str, Any]:
    """Render FC statistics for JSON output."""
    json_data = {}
    for host_name, host_data in fc_stats.items():
        if not host_data["success"]:
            json_data[host_name] = {"error": host_data["error"]}
            continue

        host_json = {}
        for group_name, group_data in host_data["grouped_stats"].items():
            group_json = {}
            for stat_name, stat_data in group_data.items():
                if "bandwidth_estimate" in stat_data:
                    group_json[stat_name] = {
                        "value": stat_data["processed"],
                        "bandwidth_estimate": stat_data["bandwidth_estimate"]
                    }
                else:
                    group_json[stat_name] = stat_data["processed"]
            host_json[group_name] = group_json
        json_data[host_name] = host_json

    return json_data


def render_fc_stats_text(fc_stats: Dict[str, Dict[str, Any]]) -> str:
    """Render FC statistics for text output."""
    output_lines = []

    for host_name, host_data in fc_stats.items():
        # Create prominent header with visual separation
        header_text = f"FIBRE CHANNEL STATISTICS - {host_name.upper()}"
        separator_line = "=" * len(header_text)

        output_lines.append("")
        output_lines.append("")
        output_lines.append(separator_line)
        output_lines.append(header_text)
        output_lines.append(separator_line)
        output_lines.append("")

        if not host_data["success"]:
            output_lines.append(f"ERROR: {host_data['error']}")
            continue

        for group_name, group_data in host_data["grouped_stats"].items():
            group_rows = []
            for stat_name, stat_data in group_data.items():
                value = stat_data["processed"]
                if "bandwidth_estimate" in stat_data:
                    value += f" ({stat_data['bandwidth_estimate']})"
                group_rows.append([stat_name, value])

            if group_rows:
                table = draw_text_table(group_name, ["Key", "Value"],
                                        group_rows)
                output_lines.append(table)
                output_lines.append("")  # Add spacing

    return "\n".join(output_lines)


def render_fc_stats_rich(fc_stats: Dict[str, Dict[str, Any]]) -> None:
    """Render FC statistics for rich output."""
    for host_name, host_data in fc_stats.items():
        console.print(f"\n[bold magenta]Statistics for "
                      f"{host_name}[/bold magenta]")

        if not host_data["success"]:
            console.print(f"[red]{host_data['error']}[/red]")
            continue

        for group_name, group_data in host_data["grouped_stats"].items():
            if not group_data:
                continue

            table = Table(title=group_name, title_style="bold blue",
                          box=box.SQUARE)
            table.add_column("Key", style="yellow")
            table.add_column("Value", style="white")

            for stat_name, stat_data in group_data.items():
                value = stat_data["processed"]
                if "bandwidth_estimate" in stat_data:
                    value += f" ({stat_data['bandwidth_estimate']})"
                table.add_row(stat_name, value)

            console.print(table)


def main() -> None:
    """
    Main entry point - scan for SFP transceivers and FC statistics.

    Discovers all FC host adapters and displays:
    1. SFP transceiver information from EEPROM
    2. FC host adapter statistics grouped by category
    """
    # Parse command line arguments
    args = parse_arguments()
    output_format = args.format
    json_pretty = args.pretty

    # Collect all data first
    sfp_data = {}
    fc_data = {}

    # Collect SFP transceiver data
    sfp_paths = glob.glob(FC_HOST_SFP_PATH_PATTERN)
    if sfp_paths:
        for path in sfp_paths:
            sfp_data[path] = collect_sfp_eeprom_data(path)

    # Collect FC statistics
    fc_data = collect_fc_statistics()

    # Render output based on format
    if output_format == "json":
        # Build complete JSON structure
        json_output = {}

        # Add SFP data
        if sfp_data:
            json_output["sfp_transceivers"] = {}
            for path, data in sfp_data.items():
                json_output["sfp_transceivers"][path] = \
                    render_sfp_data_json(data)
        else:
            json_output["info"] = {
                "sfp_search": {
                    "message": f"No SFP EEPROM files found under "
                               f"{FC_HOST_SFP_PATH_PATTERN}"
                }
            }

        # Add FC statistics
        if fc_data:
            json_output["fc_statistics"] = render_fc_stats_json(fc_data)

        # Print JSON
        if json_pretty:
            print(json.dumps(json_output, indent=2, sort_keys=True))
        else:
            print(json.dumps(json_output, sort_keys=True))

    elif output_format == "text":
        # Handle SFP data
        if sfp_data:
            for path, data in sfp_data.items():
                text_output = render_sfp_data_text(data)
                print_text_output(text_output)
                print()  # Add spacing
        else:
            msg = (f"WARNING: No SFP EEPROM files found under "
                   f"{FC_HOST_SFP_PATH_PATTERN}")
            print_text_output(msg)

        # Handle FC statistics
        if fc_data:
            fc_text = render_fc_stats_text(fc_data)
            print_text_output(fc_text)

    else:  # rich format (default)
        # Handle SFP data
        if sfp_data:
            for path, data in sfp_data.items():
                table = render_sfp_data_rich(data)
                console.print(table)
        else:
            msg = (f"[yellow]No SFP EEPROM files found under "
                   f"{FC_HOST_SFP_PATH_PATTERN}[/yellow]")
            console.print(msg)

        # Handle FC statistics
        if fc_data:
            render_fc_stats_rich(fc_data)


if __name__ == "__main__":
    main()
