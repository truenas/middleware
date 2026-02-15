import csv
import functools
import io
import glob
import os
import re

from middlewared.utils.serial import serial_port_choices


RE_DRIVER_CHOICE = re.compile(r'(\S+)\s+(\S+=\S+)?\s*(?:\((.+)\))?$')
UPS_POWERDOWN_FLAG_FILE = '/etc/killpower'


def alerts_mapping() -> dict[str, str]:
    return {
        'LOWBATT': 'UPSBatteryLow',
        'COMMBAD': 'UPSCommbad',
        'COMMOK': 'UPSCommok',
        'ONBATT': 'UPSOnBattery',
        'ONLINE': 'UPSOnline',
        'REPLBATT': 'UPSReplbatt'
    }


def port_choices(serial_console: bool, serialport: str) -> list[str]:
    ports = [
        os.path.join('/dev', port['name'])
        for port in serial_port_choices()
        if port['name'] is not None and (not serial_console or serialport != port['name'])
    ]
    ports.extend(glob.glob('/dev/uhid*'))
    ports.append('auto')
    return ports


def normalize_driver_string(driver_str: str) -> str:
    driver = driver_str.split('$')[0]
    driver = driver.split('(')[0]  # "blazer_usb (USB ID 0665:5161)"
    driver = driver.split(' or ')[0]  # "blazer_ser or blazer_usb"
    driver = driver.replace(' ', '\n\t')  # "genericups upstype=16"
    return f'driver = {driver}'


@functools.cache
def drivers_available() -> set[str]:
    return set(os.listdir('/lib/nut'))


@functools.cache
def driver_choices() -> dict[str, str]:
    ups_choices: dict[str, str] = {}
    driver_list = '/usr/share/nut/driver.list'
    if os.path.exists(driver_list):
        with open(driver_list, 'r') as f:
            d = f.read()
        r = io.StringIO()
        for line in re.sub(r'[ \t]+', ' ', d, flags=re.M).split('\n'):
            r.write(line.strip() + '\n')
        r.seek(0)
        reader = csv.reader(r, delimiter=' ', quotechar='"')
        for row in reader:
            if len(row) == 0 or row[0].startswith('#'):
                continue
            if row[-2] == '#':
                last = -3
            else:
                last = -1
            driver_str = row[last]
            driver_options = ''
            driver_annotation = ''
            # We want to match following strings
            # genericups upstype=1
            # powerman-pdu (experimental)
            m = RE_DRIVER_CHOICE.match(driver_str)
            if m:
                driver_str = m.group(1)
                driver_options = m.group(2) or ''
                driver_annotation = m.group(3) or ''
            for driver in driver_str.split(' or '):  # can be "blazer_ser or blazer_usb"
                driver = driver.strip()
                if driver not in drivers_available():
                    continue
                for i, field in enumerate(list(row)):
                    row[i] = field
                key = '$'.join([driver + (f' {driver_options}' if driver_options else ''), row[3]])
                val = f'{ups_choices[key]} / ' if key in ups_choices else ''
                ups_choices[key] = val + '%s (%s)' % (
                    ' '.join(filter(None, row[0:last])),
                    ', '.join(filter(None, [driver, driver_annotation]))
                )
    return ups_choices
