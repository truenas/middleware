import os
import re
import subprocess

HA_MODE_FILE = '/tmp/.ha_mode'


def ha_mode():

    if os.path.exists(HA_MODE_FILE):
        with open(HA_MODE_FILE, 'r') as f:
            data = f.read()
        return data.strip()

    # Temporary workaround for VirtualBOX
    proc = subprocess.Popen([
        '/usr/local/sbin/dmidecode',
        '-s', 'bios-version',
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    bios = proc.communicate()[0].strip()
    if bios == 'VirtualBox':
        proc = subprocess.Popen([
            '/usr/local/sbin/dmidecode',
            '-s', 'system-uuid',
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        systemuuid = proc.communicate()[0].strip()
        if systemuuid == 'B9E1B270-1B0C-48C7-99C8-BFB965D71584':
            node = 'A'
        else:
            node = 'B'
    else:
        proc = subprocess.Popen([
            '/usr/sbin/getencstat',
            '-v', '/dev/ses0',
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        encstat = proc.communicate()[0].strip()
        reg = re.search(r"3U20D-Encl-[AB]'", encstat, re.M)
        node = reg.group(1) if reg else None

    if node:
        mode = 'ECHOSTREAM:%s' % node
        with open(HA_MODE_FILE, 'w') as f:
            f.write(mode)
        return mode

    proc = subprocess.Popen([
        '/usr/local/sbin/dmidecode',
        '-s', 'system-serial-number',
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    serial = proc.communicate()[0].strip()

    # Laziest import as possible
    from freenasUI.support.utils import get_license
    license, error = get_license()

    if license is not None:
        if license.system_serial == serial:
            node = 'A'
        elif license.system_serial_ha == serial:
            node = 'B'

    if node is None:
        mode = 'MANUAL'
        with open(HA_MODE_FILE, 'w') as f:
            f.write(mode)
        return mode

    proc = subprocess.Popen([
        '/usr/local/sbin/dmidecode',
        '-s', 'baseboard-product-name',
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    board = proc.communicate()[0].strip()
    # Check for SBB
    # Everything else is called ULTIMATE since we can't realiably determine it
    hardware = 'SBB' if board == 'X8DTS' else 'ULTIMATE'

    mode = '%s:%s' % (hardware, node)
    with open(HA_MODE_FILE, 'w') as f:
        f.write(mode)
    return mode


def ha_node():

    if os.path.exists(HA_MODE_FILE):
        with open(HA_MODE_FILE, 'r') as f:
            data = f.read()
    else:
        data = ha_mode()

    if ':' not in data:
        return None

    return data.split(':', 1)[-1]


def ha_hardware():

    if os.path.exists(HA_MODE_FILE):
        with open(HA_MODE_FILE, 'r') as f:
            data = f.read()
    else:
        data = ha_mode()
    return data.split(':')[0]


if __name__ == '__main__':
    print ha_mode()
