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

    hardware = None
    node = None

    proc = subprocess.Popen([
        '/usr/local/sbin/dmidecode',
        '-s', 'system-product-name',
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    manufacturer = proc.communicate()[0].strip()

    if manufacturer == b"BHYVE":
        hardware = "BHYVE"
        proc = subprocess.Popen(
            ['/sbin/camcontrol', 'inquiry', 'pass0'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        inq = proc.communicate()[0].decode(errors='ignore')
        if proc.returncode == 0:
            if 'TrueNAS_A' in inq:
                node = 'A'
            else:
                node = 'B'

    else:
        enclosures = ["/dev/" + enc for enc in os.listdir("/dev") if enc.startswith("ses")]
        for enclosure in enclosures:
            proc = subprocess.Popen([
                '/usr/sbin/getencstat',
                '-V', enclosure,
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            encstat = proc.communicate()[0].decode('utf8', 'ignore').strip()
            # The echostream E16 JBOD and the echostream Z-series chassis are the same piece of hardware
            # One of the only ways to differentiate them is to look at the enclosure elements in detail
            # The Z-series chassis identifies element 0x26 as SD_9GV12P1J_12R6K4.  The E16 does not.
            # The E16 identifies element 0x25 as NM_3115RL4WB66_8R5K5
            # We use this fact to ensure we are looking at the internal enclosure, not a shelf.
            # If we used a shelf to determine which node was A or B you could cause the nodes to switch
            # identities by switching the cables for the shelf.
            if re.search("SD_9GV12P1J_12R6K4", encstat, re.M):
                hardware = 'ECHOSTREAM'
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
            # Identify PUMA platform by one of enclosure names.
            elif re.search("Enclosure Name: CELESTIC (P3215-O|P3217-B)", encstat, re.M):
                hardware = 'PUMA'
                # Identify node by comparing addresses from SES and SMP.
                # There is no exact match, but allocation seems sequential.
                proc = subprocess.Popen([
                    '/sbin/camcontrol', 'smpphylist', enclosure, '-q'
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf8')
                phylist = proc.communicate()[0].strip()
                reg = re.search(r"ESCE A_(5[0-9A-F]{15})", encstat, re.M)
                if reg:
                    addr = "0x%016x" % (int(reg.group(1), 16) - 1)
                    if addr in phylist:
                        node = "A"
                        break
                reg = re.search(r"ESCE B_(5[0-9A-F]{15})", encstat, re.M)
                if reg:
                    addr = "0x%016x" % (int(reg.group(1), 16) - 1)
                    if addr in phylist:
                        node = "B"
                        break
            else:
                # Identify ECHOWARP platform by one of enclosure names.
                reg = re.search("Enclosure Name: (ECStream|iX) 4024S([ps])", encstat, re.M)
                if reg:
                    hardware = 'ECHOWARP'
                    # Identify node by the last symbol of the model name
                    if reg.group(2) == "p":
                        node = "A"
                        break
                    elif reg.group(2) == "s":
                        node = "B"
                        break

    if node:
        mode = '%s:%s' % (hardware, node)
        with open(HA_MODE_FILE, 'w') as f:
            f.write(mode)
        return mode

    proc = subprocess.Popen([
        '/usr/local/sbin/dmidecode',
        '-s', 'system-serial-number',
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf8')
    serial = proc.communicate()[0].split('\n', 1)[0].strip()

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
        mode = None
        proc = subprocess.Popen([
            '/usr/local/sbin/dmidecode',
            '-s', 'baseboard-product-name',
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf8')
        board = proc.communicate()[0].split('\n', 1)[0].strip()
        # If we've gotten this far it's because we were unable to
        # identify ourselves via enclosure device.
        if board == 'X8DTS':
            hardware = 'SBB'
        elif board.startswith('X8'):
            hardware = 'ULTIMATE'
        else:
            mode = 'MANUAL'

        if mode is None:
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
