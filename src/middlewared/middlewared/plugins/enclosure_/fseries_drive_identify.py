from subprocess import run, PIPE, STDOUT

from middlewared.service_exception import CallError


def get_cmd(slot, status):
    base = [
        'ipmi-raw',
        '0x0',  # LUN
        '0x3c',  # NETFN
        None,  # CMD
        '0x01',  # SUBCMD
        slot,  # slot to perform action upon
        None,  # ACTION
    ]
    final = []
    if status == 'CLEAR':
        # command to clear identify led (blue)
        clear_ident = base[:]
        clear_ident[-4] = '0x22'
        clear_ident[-1] = '0x00'
        final.append(clear_ident[:])

        # command to clear fault led (yellow)
        clear_fault = base[:]
        clear_fault[-4] = '0x39'
        clear_fault[-1] = '0x00'
        final.append(clear_fault[:])
    elif status in ('IDENT', 'IDENTIFY'):
        # turn blue led on
        ident = base[:]
        ident[-4] = '0x22'
        ident[-1] = '0x01'
        final.append(ident[:])
    elif status == 'FAULT':
        # turn yellow led on
        fault = base[:]
        fault[-4] = '0x39'
        fault[-1] = '0x01'
        final.append(fault[:])
    else:
        raise ValueError(f'Invalid status: {status!r}')

    return final


def set_slot_status(slot, status):
    """Will send a command `status` to toggle the LED drive bay for a given `slot`"""
    if slot < 1 or slot > 24:
        raise ValueError(f'Invalid slot: {slot!r}')

    for cmd in get_cmd(hex(slot), status):
        ret = run(cmd, stdout=PIPE, stderr=STDOUT)
        if ret.returncode != 0:
            raise CallError(f'Failed to run {cmd!r}: {ret.stderr.decode()}')
