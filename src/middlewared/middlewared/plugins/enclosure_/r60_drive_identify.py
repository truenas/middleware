# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from subprocess import run


def slot_to_group_and_bitmask_mapping(slot: int) -> tuple[str, str]:
    """Get the group selector and drive bitmask associated with an HDD."""
    mapping = {
        # Group 0x60 (HDDs 0-3, Physical drives 1-4)
        1: ('0x60', '0x03'),
        7: ('0x60', '0x0C'),
        2: ('0x60', '0x30'),
        8: ('0x60', '0xC0'),
        # Group 0x61 (HDDs 4-7, Physical drives 5-8)
        3: ('0x61', '0x03'),
        9: ('0x61', '0x0C'),
        4: ('0x61', '0x30'),
        10: ('0x61', '0xC0'),
        # Group 0x62 (HDDs 8-11, Physical drives 9-12)
        5: ('0x62', '0x03'),
        11: ('0x62', '0x0C'),
        6: ('0x62', '0x30'),
        12: ('0x62', '0xC0'),
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

    # Enable BMC LED function
    # Prerequisite for using BMC LED commands
    run('ipmitool raw 0x06 0x52 0x11 0x20 0x00 0xD1 0x01', check=False, shell=True)  # 0x01 = "ON"
    group_selector, bitmask = slot_to_group_and_bitmask_mapping(slot)
    if led_status_mapping(status):
        # Flash the slot's LED green and yellow
        run(f'ipmitool raw 0x06 0x52 0x11 0xF0 0x00 {group_selector} {bitmask}', check=False, shell=True)
    else:
        # Turn off the whole slot group's LEDs by clearing the bits
        run(f'ipmitool raw 0x06 0x52 0x11 0xF0 0x00 {group_selector} 0x00', check=False, shell=True)
