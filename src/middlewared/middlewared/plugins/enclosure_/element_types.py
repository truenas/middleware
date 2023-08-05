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
    if (result := [k for k, v in values.items() if v]):
        return ', '.join(result)


def comm(value_raw):
    values = {
        'Identify on': (value_raw >> 16) & 0x80,
        'Fail on': (value_raw >> 16) & 0x40,
        'Disabled': value_raw & 0x01,
    }
    if (result := [k for k, v in values.items() if v]):
        return ', '.join(result)


def current(value_raw):
    values = {
        'Identify on': (value_raw >> 16) & 0x80,
        'Fail on': (value_raw >> 16) & 0x40,
        'Warn Over': (value_raw >> 16) & 0x8,
        'Crit Over': (value_raw >> 16) & 0x2,
    }
    return ', '.join([f'{(value_raw & 0xffff) / 100}A'] + [k for k, v in values.items() if v])


def enclosure(value_raw):
    values = {
        'Identify on': (value_raw >> 16) & 0x80,
        'Fail on': (value_raw >> 8) & 0x02,
        'Warn On': (value_raw >> 8) & 0x01,
    }
    result = [k for k, v in values.items() if v]
    if (pctime := (value_raw >> 10) & 0x3f):
        potime = (value_raw >> 2) & 0x3f
        result.append(f'Power cycle {pctime}min, power off for {potime}min')

    return ', '.join(result) or None


def volt(value_raw):
    values = {
        'Identify on': (value_raw >> 16) & 0x80,
        'Fail on': (value_raw >> 16) & 0x40,
        'Warn over': (value_raw >> 16) & 0x8,
        'Warn under': (value_raw >> 16) & 0x4,
        'Crit over': (value_raw >> 16) & 0x2,
        'Crit under': (value_raw >> 16) & 0x1,
    }
    return ', '.join([f'{((value_raw & 0xffff) / 100)}V'] + [k for k, v in values.items() if v])


def cooling(value_raw):
    return f'{(((value_raw & 0x7ff00) >> 8) * 10)} RPM'


def temp(value_raw):
    temp = None
    if (temp := (value_raw & 0xff00) >> 8):
        # 8 bits represents -19C to +235C
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
    return ', '.join([k for k, v in values.items() if v]) or None


def array_dev(value_raw):
    values = {
        'Identify on': (value_raw >> 8) & 0x2,
        'Fault on': value_raw & 0x20,
    }
    return ', '.join([k for k, v in values.items() if v]) or None


def sas_conn(value_raw):
    conn_type = (value_raw >> 16) & 0x7f
    values = {
        0x0: 'No information',
        0x1: 'SAS 4x receptacle (SFF-8470) [max 4 phys]',
        0x2: 'Mini SAS 4x receptacle (SFF-8088) [max 4 phys]',
        0x3: 'QSFP+ receptacle (SFF-8436) [max 4 phys]',
        0x4: 'Mini SAS 4x active receptacle (SFF-8088) [max 4 phys]',
        0x5: 'Mini SAS HD 4x receptacle (SFF-8644) [max 4 phys]',
        0x6: 'Mini SAS HD 8x receptacle (SFF-8644) [max 8 phys]',
        0x7: 'Mini SAS HD 16x receptacle (SFF-8644) [max 16 phys]',
        0xf: 'Vendor specific external connector',
        0x10: 'SAS 4i plug (SFF-8484) [max 4 phys]',
        0x11: 'Mini SAS 4i receptacle (SFF-8087) [max 4 phys]',
        0x12: 'Mini SAS HD 4i receptacle (SFF-8643) [max 4 phys]',
        0x13: 'Mini SAS HD 8i receptacle (SFF-8643) [max 8 phys]',
        0x20: 'SAS Drive backplane receptacle (SFF-8482) [max 2 phys]',
        0x21: 'SATA host plug [max 1 phy]',
        0x22: 'SAS Drive plug (SFF-8482) [max 2 phys]',
        0x23: 'SATA device plug [max 1 phy]',
        0x24: 'Micro SAS receptacle [max 2 phys]',
        0x25: 'Micro SATA device plug [max 1 phy]',
        0x26: 'Micro SAS plug (SFF-8486) [max 2 phys]',
        0x27: 'Micro SAS/SATA plug (SFF-8486) [max 2 phys]',
        0x2f: 'SAS virtual connector [max 1 phy]',
        0x3f: 'Vendor specific internal connector',
    }
    values.update({i: 'unknown external connector type: {hex(i)}' for i in range(0x8, 0xf)})
    values.update({i: 'unknown internal wide connector type: {hex(i)}' for i in range(0x14, 0x20)})
    values.update({i: 'unknown internal connector to end device type: {hex(i)}' for i in range(0x28, 0x2f)})
    values.update({i: 'reserved for internal connector type: {hex(i)}' for i in range(0x30, 0x3f)})
    values.update({i: 'reserved connector type: {hex(i)}' for i in range(0x40, 0x70)})
    values.update({i: 'vendor specific connector type: {hex(i)}' for i in range(0x70, 0x80)})

    return ', '.join(
        [values.get(conn_type, f'unexpected connector type: {hex(conn_type)}')] +
        ['Fail On'] if value_raw & 0x40 else []
    )


def sas_exp(value_raw):
    values = {
        'Identify on': (value_raw >> 16) & 0x80,
        'Fail on': (value_raw >> 16) & 0x40,
    }
    return ', '.join([k for k, v in values.items() if v]) or None


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
    17: 'OK, Swapped',
    21: 'Not Installed, Swapped',
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
