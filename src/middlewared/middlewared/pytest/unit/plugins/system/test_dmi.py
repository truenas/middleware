from middlewared.plugins.system_.dmi import SystemService
from middlewared.service import Service


full_dmi = ("""
# dmidecode 3.3
Getting SMBIOS data from sysfs.
SMBIOS 3.2.1 present.

Handle 0x0001, DMI type 1, 27 bytes
System Information
        Manufacturer: iXsystems
        Product Name: TRUENAS-M60
        Version: 0123456789
        Serial Number: A1-111111
        UUID: 00000000-0000-0000-0000-3cecef5ee7d6
        Wake-up Type: Power Switch
        SKU Number: To be filled by O.E.M.
        Family: To be filled by O.E.M.

Handle 0x0002, DMI type 2, 15 bytes
Base Board Information
        Manufacturer: Supermicro
        Product Name: X11SPH-nCTPF
        Version: 1.01
        Serial Number: 0000000000000
        Asset Tag: To be filled by O.E.M.
        Features:
                Board is a hosting board
                Board is replaceable
        Location In Chassis: To be filled by O.E.M.
        Chassis Handle: 0x0003
        Type: Motherboard
        Contained Object Handles: 0

Handle 0x0024, DMI type 16, 23 bytes
Physical Memory Array
        Location: System Board Or Motherboard
        Use: System Memory
        Error Correction Type: Single-bit ECC
        Maximum Capacity: 2304 GB
        Error Information Handle: Not Provided
        Number Of Devices: 4

Handle 0x002C, DMI type 16, 23 bytes
Physical Memory Array
        Location: System Board Or Motherboard
        Use: System Memory
        Error Correction Type: Single-bit ECC
        Maximum Capacity: 2304 GB
        Error Information Handle: Not Provided
        Number Of Devices: 4

""").splitlines()

no_dmi = ("""
# dmidecode 3.2
Scanning /dev/mem for entry point.
# No SMBIOS nor DMI entry point found, sorry.
""").splitlines()


def test__full_dmi_parse():
    expected_result = {
        'ecc-memory': True,
        'baseboard-manufacturer': 'Supermicro',
        'baseboard-product-name': 'X11SPH-nCTPF',
        'system-manufacturer': 'iXsystems',
        'system-product-name': 'TRUENAS-M60',
        'system-serial-number': 'A1-111111',
        'system-version': '0123456789',
    }
    obj = SystemService(Service)
    obj._parse_dmi(full_dmi)
    assert obj.CACHE == expected_result


def test__no_dmi_parse():
    expected_result = {
        'ecc-memory': '',
        'baseboard-manufacturer': '',
        'baseboard-product-name': '',
        'system-manufacturer': '',
        'system-product-name': '',
        'system-serial-number': '',
        'system-version': '',
    }
    obj = SystemService(Service)
    obj._parse_dmi(no_dmi)
    assert obj.CACHE == expected_result
