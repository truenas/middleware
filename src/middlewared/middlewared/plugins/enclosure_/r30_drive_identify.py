# Copyright (c) - iXsystems Inc.
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from subprocess import run

NVME_CONTROLLERS = ('0xc0', '0xc2', '0xc4')


def slot_to_controller_and_bay_mapping(slot):
    mapping = {
        # bays 1-8
        1: (NVME_CONTROLLERS[0], '0x01'),
        2: (NVME_CONTROLLERS[0], '0x04'),
        3: (NVME_CONTROLLERS[0], '0x10'),
        4: (NVME_CONTROLLERS[0], '0x40'),
        5: (NVME_CONTROLLERS[1], '0x01'),
        6: (NVME_CONTROLLERS[1], '0x04'),
        7: (NVME_CONTROLLERS[0], '0x02'),
        8: (NVME_CONTROLLERS[0], '0x08'),
        # bays 9-12
        9: (NVME_CONTROLLERS[0], '0x20'),
        10: (NVME_CONTROLLERS[0], '0x80'),
        11: (NVME_CONTROLLERS[1], '0x02'),
        12: (NVME_CONTROLLERS[1], '0x08'),
        # bays 13-16
        13: (NVME_CONTROLLERS[2], '0x04'),
        14: (NVME_CONTROLLERS[2], '0x01'),
        15: (NVME_CONTROLLERS[2], '0x08'),
        16: (NVME_CONTROLLERS[2], '0x02'),
    }
    try:
        return mapping[slot]
    except KeyError:
        raise ValueError(f'{slot!r} is invalid')


def led_status_mapping(status):
    mapping = {
        'OFF': '0x00',
        'CLEAR': '0x00',  # turn off red led
        'IDENTIFY': '0x42',  # red and green led blink fast
        'ON': '0x42',  # same as IDENTIFY
    }
    try:
        return mapping[status]
    except KeyError:
        raise ValueError(f'{status!r} is invalid')


def set_slot_status(slot, status):
    """
    Unfortunately, there is no way to query current drive identification status.
    Also, there is no way to turn off a singular LED bay, you have to clear the
    controller (nvme bank) of drives.
    """
    ctrl, bay = slot_to_controller_and_bay_mapping(slot)
    led_status_mapping(status)  # will crash if invalid status is passed to us

    # always disable BMC sensor scan
    run('ipmitool raw 0x30 0x02 0x00', check=False, shell=True)
    # always switch to SMBUS
    run('ipmitool raw 0x06 0x52 0x07 0xe6 0x0 0x4 0x4', check=False, shell=True)
    if status in ('OFF', 'CLEAR'):
        for i in ('0xc0', '0xc2', '0xc4'):
            # set to manual mode for the nvme controller
            run(f'ipmitool raw 0x06 0x52 0x07 {i} 0x00 0x3c 0xff', shell=True)
            # clear all the bank of LEDs on the controller (no way to turn off specific drive)
            run(f'ipmitool raw 0x06 0x52 0x07 {i} 0x00 {led_status_mapping("ON")} 0x00', shell=True)
    else:
        # set to manual mode for the nvme controller
        run(f'ipmitool raw 0x06 0x52 0x07 {ctrl} 0x00 0x3c 0xff', shell=True)
        # light up the slot
        run(f'ipmitool raw 0x06 0x52 0x07 {ctrl} 0x00 {led_status_mapping("ON")} {bay}', shell=True)
