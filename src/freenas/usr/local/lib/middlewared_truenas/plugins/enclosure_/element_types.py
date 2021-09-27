def alarm(value_raw):
    values = {
        'Identify on': (value_raw >> 16) & 0x80,
        'Fail on': (value_raw >> 16) & 0x40,
        'RQST mute': value_raw & 0x80,
        'Muted': value_raw & 0x40,
        'Remind': value_raw & 0x10,
        'INFO': value_raw & 0x08,
        'NON-CRIT': value_raw & 0x04,
        'CRIT': value_raw & 0x02,
        'UNRECOV': value_raw & 0x01,
    }

    result = [k for k, v in values.items() if v]
    if not result:
        return 'None'
    return ', '.join(result)


def comm(value_raw):
    values = {
        'Identify on': (value_raw >> 16) & 0x80,
        'Fail on': (value_raw >> 16) & 0x40,
        'Disabled': value_raw & 0x01,
    }

    result = [k for k, v in values.items() if v]
    if not result:
        return 'None'
    return ', '.join(result)


def current(value_raw):
    values = {
        'Identify on': (value_raw >> 16) & 0x80,
        'Fail on': (value_raw >> 16) & 0x40,
        'Warn Over': (value_raw >> 16) & 0x8,
        'Crit Over': (value_raw >> 16) & 0x2,
    }
    amp = f'{(value_raw & 0xffff) / 100}A'

    result = [k for k, v in values.items() if v]
    result.insert(0, amp)
    return ', '.join(result)


def enclosure(value_raw):
    values = {
        'Identify on': (value_raw >> 16) & 0x80,
        'Fail on': (value_raw >> 8) & 0x02,
        'Warn On': (value_raw >> 8) & 0x01,
    }
    pctime = (value_raw >> 10) & 0x3f
    potime = (value_raw >> 2) & 0x3f
    pc_po = ''
    if pctime:
        pc_po = f'Power cycle {pctime}min, power off for {potime}min'

    result = [k for k, v in values.items() if v]
    result.append(pc_po) if pc_po else None
    if not result:
        return 'None'
    return ', '.join(result)


def volt(value_raw):
    values = {
        'Identify on': (value_raw >> 16) & 0x80,
        'Fail on': (value_raw >> 16) & 0x40,
        'Warn over': (value_raw >> 16) & 0x8,
        'Warn under': (value_raw >> 16) & 0x4,
        'Crit over': (value_raw >> 16) & 0x2,
        'Crit under': (value_raw >> 16) & 0x1,
    }
    volts = f'{((value_raw & 0xffff) / 100)}V'

    result = [k for k, v in values.items() if v]
    result.insert(0, volts)
    if not result:
        return 'None'
    return ', '.join(result)


def cooling(value_raw):
    return f'{(((value_raw & 0x7ff00) >> 8) * 10)} RPM'


def temp(value_raw):
    temp = (value_raw & 0xff00) >> 8
    if not temp:
        temp = None
    else:
        # 8 bites represents -19C to +235C
        # value of 0 would imply -20C
        temp = f'{temp -20}C'
    return temp


def psu(value_raw):
    values = {
        'Identify on': (value_raw >> 16) & 0x80,
        'Fail on': value_raw & 0x40,
        'DC overvoltage': (value_raw >> 8) & 0x8,
        'DC undervoltage': (value_raw >> 8) & 0x4,
        'DC overcurrent': (value_raw >> 8) & 0x2,
        'Overtemp fail': value_raw & 0x8,
        'Overtemp warn': value_raw & 0x4,
        'AC fail': value_raw & 0x2,
        'DC fail': value_raw & 0x1,
        'Off': value_raw & 0x10,
    }
    result = [k for k, v in values.items() if v]
    if not result:
        return 'None'
    return ', '.join(result)


def array_dev(value_raw):
    values = {
        'Identify on': (value_raw >> 8) & 0x2,
        'Fault on': value_raw & 0x20,
    }
    result = [k for k, v in values.items() if v]
    if not result:
        return 'None'
    return ', '.join(result)


def sas_conn(value_raw):
    conn_type = (value_raw >> 16) & 0x7f
    value = ''
    if conn_type == 0x0:
        value = 'No information'
    elif conn_type == 0x1:
        value = 'SAS 4x receptacle (SFF-8470) [max 4 phys]'
    elif conn_type == 0x2:
        value = 'Mini SAS 4x receptacle (SFF-8088) [max 4 phys]'
    elif conn_type == 0x3:
        value = 'QSFP+ receptacle (SFF-8436) [max 4 phys]'
    elif conn_type == 0x4:
        value = 'Mini SAS 4x active receptacle (SFF-8088) [max 4 phys]'
    elif conn_type == 0x5:
        value = 'Mini SAS HD 4x receptacle (SFF-8644) [max 4 phys]'
    elif conn_type == 0x6:
        value = 'Mini SAS HD 8x receptacle (SFF-8644) [max 8 phys]'
    elif conn_type == 0x7:
        value = 'Mini SAS HD 16x receptacle (SFF-8644) [max 16 phys]'
    elif conn_type == 0xf:
        value = 'Vendor specific external connector'
    elif conn_type == 0x10:
        value = 'SAS 4i plug (SFF-8484) [max 4 phys]'
    elif conn_type == 0x11:
        value = 'Mini SAS 4i receptacle (SFF-8087) [max 4 phys]'
    elif conn_type == 0x12:
        value = 'Mini SAS HD 4i receptacle (SFF-8643) [max 4 phys]'
    elif conn_type == 0x13:
        value = 'Mini SAS HD 8i receptacle (SFF-8643) [max 8 phys]'
    elif conn_type == 0x20:
        value = 'SAS Drive backplane receptacle (SFF-8482) [max 2 phys]'
    elif conn_type == 0x21:
        value = 'SATA host plug [max 1 phy]'
    elif conn_type == 0x22:
        value = 'SAS Drive plug (SFF-8482) [max 2 phys]'
    elif conn_type == 0x23:
        value = 'SATA device plug [max 1 phy]'
    elif conn_type == 0x24:
        value = 'Micro SAS receptacle [max 2 phys]'
    elif conn_type == 0x25:
        value = 'Micro SATA device plug [max 1 phy]'
    elif conn_type == 0x26:
        value = 'Micro SAS plug (SFF-8486) [max 2 phys]'
    elif conn_type == 0x27:
        value = 'Micro SAS/SATA plug (SFF-8486) [max 2 phys]'
    elif conn_type == 0x2f:
        value = 'SAS virtual connector [max 1 phy]'
    elif conn_type == 0x3f:
        value = 'Vendor specific internal connector'
    else:
        _hex = f'0x{conn_type:0x}'
        if conn_type < 0x10:
            value = f'unknown external connector type: {_hex}'
        elif conn_type < 0x20:
            value = f'unknown internal wide connector type: {_hex}'
        elif conn_type < 0x30:
            value = f'unknown internal connector to end device, type: {_hex}'
        elif conn_type < 0x3f:
            value = f'reserved for internal connector, type: {_hex}'
        elif conn_type < 0x70:
            value = f'reserved connector type: {_hex}'
        elif conn_type < 0x80:
            value = f'vendor specific connector type: {_hex}'
        else:
            value = f'unexpected connector type: {_hex}'

    result = [value]
    result.append('Fail On') if value_raw & 0x40 else None
    return ', '.join(result)


def sas_exp(value_raw):
    values = {
        'Identify on': (value_raw >> 16) & 0x80,
        'Fail on': (value_raw >> 16) & 0x40,
    }
    result = [k for k, v in values.items() if v]
    if not result:
        return 'None'
    return ', '.join(result)


ELEMENT_DESC = {
    0: 'Unsupported',
    1: 'OK',
    2: 'Critical',
    3: 'Noncritical',
    4: 'Unrecoverable',
    5: 'Not installed',
    6: 'Unknown',
    7: 'Not available',
    8: 'No access allowed',
    9: 'reserved [9]',
    10: 'reserved [10]',
    11: 'reserved [11]',
    12: 'reserved [12]',
    13: 'reserved [13]',
    14: 'reserved [14]',
    15: 'reserved [15]',
    17: 'OK, Swapped'
}

ELEMENT_TYPES = {
    0: ('Unspecified', lambda *args: None),
    1: ('Device Slot', lambda *args: None),
    2: ('Power Supply', psu),
    3: ('Cooling', cooling),
    4: ('Temperature Sensors', temp),
    5: ('Door Lock', lambda *args: None),
    6: ('Audible Alarm', alarm),
    7: ('Enclosure Services Controller Electronics', lambda *args: None),
    8: ('SCC Controller Electronics', lambda *args: None),
    9: ('Nonvolatile Cache', lambda *args: None),
    10: ('Invalid Operation Reason', lambda *args: None),
    11: ('Uninterruptible Power Supply', lambda *args: None),
    12: ('Display', lambda *args: None),
    13: ('Key Pad Entry', lambda *args: None),
    14: ('Enclosure', enclosure),
    15: ('SCSI Port/Transciever', lambda *args: None),
    16: ('Language', lambda *args: None),
    17: ('Communication Port', comm),
    18: ('Voltage Sensor', volt),
    19: ('Current Sensor', current),
    20: ('SCSI Target Port', lambda *args: None),
    21: ('SCSI Initiator Port', lambda *args: None),
    22: ('Simple Subenclosure', lambda *args: None),
    23: ('Array Device Slot', array_dev),
    24: ('SAS Expander', sas_exp),
    25: ('SAS Connector', sas_conn),
}
