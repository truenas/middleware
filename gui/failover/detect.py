import os
import re
import sys
import subprocess

HA_MODE_FILE = '/tmp/.ha_mode'


def ha_mode():

    if os.path.exists(HA_MODE_FILE):
        with open(HA_MODE_FILE, 'r') as f:
            data = f.read().strip()
        return data

    # Temporary workaround for VirtualBOX
    #proc = subprocess.Popen([
    #    '/usr/local/sbin/dmidecode',
    #    '-s', 'bios-version',
    #], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    #bios = proc.communicate()[0].strip()
    #if bios == 'VirtualBox':
    if False:
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
        enclosures = ["/dev/" + enc for enc in os.listdir("/dev") if enc.startswith("ses")]
        # The echostream E16 JBOD and the echostream Z-series chassis are the same piece of hardware
        # One of the only ways to differentiate them is to look at the enclosure elements in detail
        # The Z-series chassis identifies element 0x26 as SD_9GV12P1J_12R6K4.  The E16 does not.
        # The E16 identifies element 0x25 as NM_3115RL4WB66_8R5K5
        # We use this fact to ensure we are looking at the internal enclosure, not a shelf.
        # If we used a shelf to determine which node was A or B you could cause the nodes to switch
        # identities by switching the cables for the shelf.
        ECHOSTREAM_MAGIC = "SD_9GV12P1J_12R6K4"
        for enclosure in enclosures:
            proc = subprocess.Popen([
                '/usr/sbin/getencstat',
                '-v', enclosure,
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            encstat = proc.communicate()[0].strip()
            echostream = re.search(ECHOSTREAM_MAGIC, encstat, re.M)
            if echostream:
                reg = re.search(r"3U20D-Encl-([AB])'", encstat, re.M)
                # In theory this should only be reached if we are dealing with
                # an echostream, which renders the "if reg else None" irrelevent
                node = reg.group(1) if reg else None
                # We should never be able to find more than one of these
                # but just in case we ever have a situation where there are
                # multiple internal enclosures, we'll just stop at the first one
                # we find.
                if node:
                    break
            else:
                # No echostream enclosures were detected
                node = None
        else:
            # No enclosures were detected at all
            node = None

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

    if license.system_serial and license.system_serial_ha:
        proc = subprocess.Popen([
            '/usr/local/sbin/dmidecode',
            '-s', 'baseboard-product-name',
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        board = proc.communicate()[0].strip()
        # If we've gotten this far it's because we were unable to
        # detect ourselves as an echostream.
        if board == 'LIBRA':
            hardware = 'AIC'
        elif board == 'X8DTS':
            hardware = 'SBB'
        else:
            # At this point we are not an echostream or an SBB or an AIC
            # however before we call ourselves an ULTIMATE we are going
            # to check for X8 versus X9 hardware.  All ultimates were
            # SM X8 so if we are not an X8...something is wrong.
            if board.startswith('X8'):
                hardware = 'ULTIMATE'
            else:
                hardware = 'FAULT'

        mode = '%s:%s' % (hardware, node)
        with open(HA_MODE_FILE, 'w') as f:
            f.write(mode)
        return mode
    else:
        mode = 'MANUAL'
        with open(HA_MODE_FILE, 'w') as f:
            f.write(mode)
        return mode


def ha_node():

    if os.path.exists(HA_MODE_FILE):
        with open(HA_MODE_FILE, 'r') as f:
            data = f.read().strip()
    else:
        data = ha_mode()

    if ':' not in data:
        return None

    return data.split(':', 1)[-1]


def ha_hardware():

    if os.path.exists(HA_MODE_FILE):
        with open(HA_MODE_FILE, 'r') as f:
            data = f.read().strip()
    else:
        data = ha_mode()
    return data.split(':')[0]


if __name__ == '__main__':
    if '/usr/local/www' not in sys.path:
        sys.path.append('/usr/local/www')
    print(ha_mode())
