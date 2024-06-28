from .enums import ElementStatus, ElementType


def alarm(value_raw):
    """See SES-4 7.3.8 Audible Alarm element, Table 98 — Audible Alarm status element

    Returns a comma-separated string for each alarm bit set or None otherwise
    """
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
    """See SES-4 7.3.19 Communication Port element, Table 140 — Communication Port status element

    Returns a comma-separated string for each comm port bit set or None otherwise
    """
    values = {
        'Identify on': (value_raw >> 16) & 0x80,
        'Fail on': (value_raw >> 16) & 0x40,
        'Disabled': value_raw & 0x01,
    }
    if (result := [k for k, v in values.items() if v]):
        return ', '.join(result)


def current(value_raw):
    """See SES-4 7.3.21 Current Sensor element, Table 148 — Current Sensor status element

    Returns a comma-separated string for each current sensor bit set or None otherwise
    """
    values = {
        'Identify on': (value_raw >> 16) & 0x80,
        'Fail on': (value_raw >> 16) & 0x40,
        'Warn over': (value_raw >> 16) & 0x8,
        'Crit over': (value_raw >> 16) & 0x2,
    }
    return ', '.join([f'{(value_raw & 0xffff) / 100}A'] + [k for k, v in values.items() if v])


def enclosure(value_raw):
    """See SES-4 7.3.16 Enclosure element, Table 130 — Enclosure status element

    Returns a comma-separated string for each status bit set as well as the
    time until power cycle and the requested time to be powered off. Otherwise
    if no bits are set, it will return None
    """
    values = {
        'Identify on': (value_raw >> 16) & 0x80,
        'Fail on': (value_raw >> 8) & 0x02,
        'Warn on': (value_raw >> 8) & 0x01,
        'RQST fail': value_raw & 0x02,
        'RQST warn': value_raw & 0x01,
    }
    result = [k for k, v in values.items() if v]
    if (pctime := (value_raw >> 10) & 0x3f):
        pctime = f'Power cycle {pctime}min'
        potime = (value_raw >> 2) & 0x3f
        if potime == 0:
            potime = ', power off until manually restored'
        else:
            potime = f', power off for {potime}min'

        result.append(f'{pctime}{potime}')

    return ', '.join(result) or None


def volt(value_raw):
    """See SES-4 7.3.20 Voltage Sensor element, Table 144 — Voltage Sensor status element

    Returns a comma-separated string for each voltage sensor bit set as well as the
    current voltage being reported. If no voltage sensor bit is set, will return
    the calculated voltage. (In Volts)
    """
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
    """See SES-4 7.3.5 Cooling element, Table 89 — Cooling status element

    Returns the rotations per minute (RPM). NOTE: we only care about these
    bits for our implementation
    """
    return f'{(((value_raw & 0x7ff00) >> 8) * 10)} RPM'


def temp(value_raw):
    """See SES-4 7.3.6 Temperature Sensor element, Table 94 — Temperature Sensor status element

    Returns a string of the calculated temperature (in celsius) for the given element. If the
    calculated temperature is 0, it would imply -20C so we return None
    """
    if (temp := (value_raw & 0xff00) >> 8):
        # 8 bits represents -19C to +235C
        # value of 0 would imply -20C
        return f'{temp - 20}C'


def psu(value_raw):
    """See SES-4 7.3.4 Power Supply element, Table 86 — Power Supply status element

    Returns a comma-separated string for each psu element sensor bit set or None otherwise
    """
    values = {
        'Identify on': (value_raw >> 16) & 0x80,
        'Do not remove': (value_raw >> 16) & 0x40,
        'DC overvoltage': (value_raw >> 8) & 0x8,
        'DC undervoltage': (value_raw >> 8) & 0x4,
        'DC overcurrent': (value_raw >> 8) & 0x2,
        'Hot swap': value_raw & 0x80,
        'Fail on': value_raw & 0x40,
        'RQST on': value_raw & 0x20,
        'Off': value_raw & 0x10,
        'Overtemp fail': value_raw & 0x8,
        'Overtemp warn': value_raw & 0x4,
        'AC fail': value_raw & 0x2,
        'DC fail': value_raw & 0x1,
    }
    return ', '.join([k for k, v in values.items() if v]) or None


def array_dev(value_raw):
    """See SES-4 7.3.3 Array Device Slot element, Table 84 — Array Device Slot status element

    Returns a comma-separated string for each array device element sensor set or None otherwise

    NOTE: SES-4 spec informs us of _many_ other bits that can be set but we only care about
    the IDENT and FAULT REQSTD bits for our implementation
    """
    values = {
        'Identify on': (value_raw >> 8) & 0x2,
        'Fault on': value_raw & 0x20,
    }
    return ', '.join([k for k, v in values.items() if v]) or None


def sas_conn(value_raw):
    """See SES-4 7.3.26 SAS Connector element, Table 158 — SAS Connector status element and
    Table 159 — CONNECTOR TYPE field.

    Returns a comma separated string specifying the connector type as well as returning
    whether or not the FAIL bit is set
    """
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
        0x14: 'Mini SAS HD 16i receptacle (SFF-8643) [max 16 phys]',
        0x15: 'SlimSAS 4i (SFF-8654) [max 4 phys]',
        0x16: 'SlimSAS 8i (SFF-8654) [max 8 phys]',
        0x17: 'SAS MiniLink 4i (SFF-8612) [max 4 phys]',
        0x18: 'SAS MiniLink 8i (SFF-8612) [max 8 phys]',
        0x19: 'unknown internal wide connector type: 0x19',
        0x20: 'SAS Drive backplane receptacle (SFF-8482) [max 2 phys]',
        0x21: 'SATA host plug [max 1 phy]',
        0x22: 'SAS Drive plug (SFF-8482) [max 2 phys]',
        0x23: 'SATA device plug [max 1 phy]',
        0x24: 'Micro SAS receptacle [max 2 phys]',
        0x25: 'Micro SATA device plug [max 1 phy]',
        0x26: 'Micro SAS plug (SFF-8486) [max 2 phys]',
        0x27: 'Micro SAS/SATA plug (SFF-8486) [max 2 phys]',
        0x28: '12 Gbit/s SAS Drive backplane receptacle (SFF-8680) [max 2 phys]',
        0x29: '12 Gbit/s SAS Drive Plug (SFF-8680) [max 2 phys]',
        0x2a: 'Multifunction 12 Gbit/s 6x Unshielded receptacle connector receptacle (SFF-8639) [max 6 phys]',
        0x2b: 'Multifunction 12 Gbit/s 6x Unshielded receptacle connector plug (SFF-8639) [max 6 phys]',
        0x2c: 'SAS Multilink Drive backplane receptacle (SFF-8630) [max 4 phys]',
        0x2d: 'SAS Multilink Drive backplane plug (SFF-8630) [max 4 phys]',
        0x2e: 'unknown internal connector to end device type: 0x2e',
        0x2f: 'SAS virtual connector [max 1 phy]',
        0x3f: 'Vendor specific internal connector',
        0x40: 'SAS High Density Drive backplane receptacle (SFF-8631) [max 8 phys]',
        0x41: 'SAS High Density Drive backplane plug (SFF-8631) [max 8 phys]',
    }
    values.update({i: f'unknown external connector type: {hex(i)}' for i in range(0x8, 0xf)})
    values.update({i: f'reserved for internal connector type: {hex(i)}' for i in range(0x30, 0x3f)})
    values.update({i: f'reserved connector type: {hex(i)}' for i in range(0x42, 0x70)})
    values.update({i: f'vendor specific connector type: {hex(i)}' for i in range(0x70, 0x80)})

    formatted = [values.get(conn_type, f'unexpected connector type: {hex(conn_type)}')]
    if value_raw & 0x40:
        formatted.append('Fail on')
    return ', '.join(formatted)


def sas_exp(value_raw):
    """See SES-4 7.3.25 SAS Expander element, Table 156 — SAS Expander status element

    Returns a comma separated string for each bit set or None otherwise
    """
    values = {
        'Identify on': (value_raw >> 16) & 0x80,
        'Fail on': (value_raw >> 16) & 0x40,
    }
    return ', '.join([k for k, v in values.items() if v]) or None


# See SES-4 7.2.3 Status element format, Table 74 — ELEMENT STATUS CODE field
ELEMENT_DESC = {
    0: ElementStatus.UNSUPPORTED.value,
    1: ElementStatus.OK.value,
    2: ElementStatus.CRITICAL.value,
    3: ElementStatus.NONCRITICAL.value,
    4: ElementStatus.UNRECOVERABLE.value,
    5: ElementStatus.NOT_INSTALLED.value,
    6: ElementStatus.UNKNOWN.value,
    7: ElementStatus.NOT_AVAILABLE.value,
    8: ElementStatus.NO_ACCESS_ALLOWED.value,
    9: 'reserved [9]',
    10: 'reserved [10]',
    11: 'reserved [11]',
    12: 'reserved [12]',
    13: 'reserved [13]',
    14: 'reserved [14]',
    15: 'reserved [15]',
    # getencstat on CORE reports these last 2 statuses on the X-series enclosure
    # so while it's not in the spec, we'll just maintain backwards compatible
    # behavior
    17: 'OK, Swapped',
    21: 'Not Installed, Swapped',
}

# See SES-4 7.1 Element definitions overview, Table 71 — Element type codes
ELEMENT_TYPES = {
    0: (ElementType.UNSPECIFIED.value, lambda *args: None),
    1: (ElementType.DEVICE_SLOT.value, lambda *args: None),
    2: (ElementType.POWER_SUPPLY.value, psu),
    3: (ElementType.COOLING.value, cooling),
    4: (ElementType.TEMPERATURE_SENSORS.value, temp),
    5: (ElementType.DOOR_LOCK.value, lambda *args: None),
    6: (ElementType.AUDIBLE_ALARM.value, alarm),
    7: (ElementType.ENCLOSURE_SERVICES_CONTROLLER_ELECTRONICS.value, lambda *args: None),
    8: (ElementType.SCC_CONTROLLER_ELECTRONICS.value, lambda *args: None),
    9: (ElementType.NONVOLATILE_CACHE.value, lambda *args: None),
    10: (ElementType.INVALID_OPERATION_REASON.value, lambda *args: None),
    11: (ElementType.UNINTERRUPTIBLE_POWER_SUPPLY.value, lambda *args: None),
    12: (ElementType.DISPLAY.value, lambda *args: None),
    13: (ElementType.KEY_PAD_ENTRY.value, lambda *args: None),
    14: (ElementType.ENCLOSURE.value, enclosure),
    15: (ElementType.SCSI_PORT_TRANSCEIVER.value, lambda *args: None),
    16: (ElementType.LANGUAGE.value, lambda *args: None),
    17: (ElementType.COMMUNICATION_PORT.value, comm),
    18: (ElementType.VOLTAGE_SENSOR.value, volt),
    19: (ElementType.CURRENT_SENSOR.value, current),
    20: (ElementType.SCSI_TARGET_PORT.value, lambda *args: None),
    21: (ElementType.SCSI_INITIATOR_PORT.value, lambda *args: None),
    22: (ElementType.SIMPLE_SUBENCLOSURE.value, lambda *args: None),
    23: (ElementType.ARRAY_DEVICE_SLOT.value, array_dev),
    24: (ElementType.SAS_EXPANDER.value, sas_exp),
    25: (ElementType.SAS_CONNECTOR.value, sas_conn),
}
