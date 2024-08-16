# Copyright (c) - iXsystems Inc.
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from subprocess import run, PIPE, STDOUT

from middlewared.service_exception import CallError


def slot_to_controller_and_bay_mapping(slot):
    mapping = {
        # bays 1-8
        1: ('0xc0', '0x01'),
        2: ('0xc0', '0x02'),
        3: ('0xc0', '0x04'),
        4: ('0xc0', '0x08'),
        5: ('0xc0', '0x10'),
        6: ('0xc0', '0x20'),
        7: ('0xc0', '0x40'),
        8: ('0xc0', '0x80'),
        # bays 9-12
        9: ('0xc2', '0x01'),
        10: ('0xc2', '0x02'),
        11: ('0xc2', '0x04'),
        12: ('0xc2', '0x08'),
        # bays 13-16
        13: ('0xc4', '0x01'),
        14: ('0xc4', '0x02'),
        15: ('0xc4', '0x04'),
        16: ('0xc4', '0x08'),
    }
    try:
        return mapping[slot]
    except KeyError:
        raise ValueError(f'{slot!r} is invalid')


def led_status_mapping(status):
    mapping = {
        'CLEAR': '0x00',  # turn off red led
        'IDENTIFY': '0x42',  # red and green led blink fast
        'FAULT': '0x44',  # red led solid, green led still works as normal
        'REBUILD': '0x46',  # red led blink slow, green led still works as normal
    }
    try:
        return mapping[status]
    except KeyError:
        raise ValueError(f'{status!r} is invalid')


def set_slot_status(slot, status):
    """
    Unfortunately, there is no way to query current drive identification status.
    Furthemore, switching SMBUS back into auto mode doesn't guarantee the LEDs
    will be automatically cleared so we need to clear them manually. Finally,
    it's unclear on whether or not we even need to transition from manual to auto
    mode (and vice versa) on SMBUS so we go the safe route and always toggle it.
    Steps are as follows:
        1. switch to manual mode
        2. clear drive IDENTIFY led `bay` on `ctrl`
        3. clear drive FAULT led `bay` on `ctrl`
        4. clear drive REBUILD led `bay` on `ctrl`

        If the user has requested anything other than CLEAR for the drive bay
            5. light up the drive bay that was requested

        6. switch back to auto mode
    """
    ctrl, bay = slot_to_controller_and_bay_mapping(slot)
    status_map = led_status_mapping(status)

    base = f'ipmitool raw 0x06 0x52 0x07 {ctrl} 0x00'
    manual_mode_cmd = f'{base} 0x3c 0xff'
    clear_ident_cmd = f'{base} {led_status_mapping("IDENTIFY")} {bay}'
    clear_fault_cmd = f'{base} {led_status_mapping("FAULT")} {bay}'
    clear_rebui_cmd = f'{base} {led_status_mapping("REBUILD")} {bay}'
    cmds = [manual_mode_cmd, clear_ident_cmd, clear_fault_cmd, clear_rebui_cmd]
    if status != 'CLEAR':
        cmds.append(f'{base} {status_map} {bay}')

    # always go back to auto mode (for now)
    cmds.append(f'{base} 0x3c 0x00')

    # now subprocess (once) for the commands
    cmds = '; '.join(cmds)
    ret = run(cmds, stdout=PIPE, stderr=STDOUT, shell=True)
    if ret.returncode != 0:
        raise CallError(f'Failed to run {cmds!r}: {ret.stdout.decode()}')
