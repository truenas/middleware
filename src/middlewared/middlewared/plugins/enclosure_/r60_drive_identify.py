# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from subprocess import run


def slot_to_group_and_bitmask_mapping(slot: int) -> tuple[str, str]:
    """Get the group selector and drive bitmask associated with an HDD."""
    mapping = {
        # Group 0x60 (HDDs 0-3, Physical drives 1-4)
        1: ('0x60', '0x02'),
        7: ('0x60', '0x08'),
        2: ('0x60', '0x20'),
        8: ('0x60', '0x80'),
        # Group 0x61 (HDDs 4-7, Physical drives 5-8)
        3: ('0x61', '0x02'),
        9: ('0x61', '0x08'),
        4: ('0x61', '0x20'),
        10: ('0x61', '0x80'),
        # Group 0x62 (HDDs 8-11, Physical drives 9-12)
        5: ('0x62', '0x02'),
        11: ('0x62', '0x08'),
        6: ('0x62', '0x20'),
        12: ('0x62', '0x80'),
    }
    try:
        return mapping[slot]
    except KeyError:
        raise ValueError(f'{slot!r} is invalid. Valid slots are 1-12')


def led_status_mapping(status: str) -> bool:
    mapping = {
        'OFF': False,
        'CLEAR': False,
        'IDENTIFY': True,
        'ON': True,
    }
    try:
        return mapping[status]
    except KeyError:
        raise ValueError(f'{status!r} is invalid. Valid statuses: OFF, CLEAR, IDENTIFY, ON')


def set_slot_status(slot: int, status: str) -> None:
    """Control the LED identification for individual drive slots using the R60-specific IPMI commands."""
    # - 0x06: Network Funcion (Application)
    # - 0x52: Command (OEM/Vendor specific)
    # - 0x11 ... : Vendor-defined data bytes specific to the function
    if led_status_mapping(status):
        group_selector, bitmask = slot_to_group_and_bitmask_mapping(slot)
        # Enable BMC LED function first
        run('ipmitool raw 0x06 0x52 0x11 0x20 0x00 0xD1 0x01', check=False, shell=True)  # 0x01 = ON
        # Enable the specific drive's green LED
        run(f'ipmitool raw 0x06 0x52 0x11 0xF0 0x00 {group_selector} {bitmask}', check=False, shell=True)
    else:
        # For OFF/CLEAR, we need to disable the BMC LED function which turns off all LEDs
        run('ipmitool raw 0x06 0x52 0x11 0x20 0x00 0xD1 0x00', check=False, shell=True)  # 0x00 = OFF
