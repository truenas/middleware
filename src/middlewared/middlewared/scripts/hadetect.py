import subprocess
import pathlib
import re
import json

from licenselib.license import License

GETENCSTAT = '/usr/sbin/getencstat'
ZSERIES = 'SD_9GV12P1J_12R6K4'
XSERIES = 'Enclosure Name: CELESTIC (P3215-O|P3217-B)'
MSERIES = 'Enclosure Name: (ECStream|iX) 4024S([ps])'
LICENSE = '/data/license'


def main():
    result = {'hardware': 'MANUAL', 'node': '', 'licensed': False}
    try:
        for enclosure in pathlib.Path('/dev').iterdir():
            if not enclosure.name.startswith('ses'):
                continue

            # grab the getencstat output
            cp = subprocess.run(
                [GETENCSTAT, '-V', enclosure],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if cp.stdout:
                encstat = cp.stdout.decode('utf8', 'ignore').strip()
                if re.search(ZSERIES, encstat, re.M):
                    # echostream (Z-series)
                    result['hardware'] = 'ECHOSTREAM'

                    # now get node position
                    node = re.search(r"3U20D-Encl-([AB])'", encstat, re.M)
                    if node:
                        result['node'] = node.group(1)
                        break

                elif re.search(XSERIES, encstat, re.M):
                    # puma (X-series)
                    result['hardware'] = 'PUMA'

                    # now get node position
                    smp = subprocess.run(
                        ['/sbin/camcontrol', 'smpphylist', enclosure, '-q'],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                    if smp.stdout:
                        smp = smp.stdout.decode('utf8', 'ignore').strip()

                        regA = re.search(
                            'ESCE A_(5[0-9A-F]{15})', encstat, re.M
                        )
                        if regA:
                            addr = '0x%016x' % (int(regA.group(1), 16) - 1)
                            if addr in smp:
                                result['node'] = 'A'
                                break
                        else:
                            regB = re.search(
                                'ESCE B_(5[0-9A-F]{15})', encstat, re.M
                            )
                            if regB:
                                addr = '0x%016x' % (int(regB.group(1), 16) - 1)
                                if addr in smp:
                                    result['node'] = 'B'
                                    break
                else:
                    reg = re.search(MSERIES, encstat, re.M)
                    if reg:
                        # echowarp (M-series)
                        result['hardware'] = 'ECHOWARP'

                        # now get node position
                        if reg.group(2) == 'p':
                            result['node'] = 'A'
                            break
                        elif reg.group(2) == 's':
                            result['node'] = 'B'
                            break

        # check if this system is licensed for HA
        try:
            with pathlib.Path(LICENSE).open('r') as f:
                lic_file = f.read().strip('\n')
                lic_obj = License.load(lic_file)
                if lic_obj.system_serial_ha:
                    result['licensed'] = True
        except Exception:
            pass

    except Exception:
        # this script is called as a fallback mechanism in
        # ix-netif rc script so if any type of error occurs
        # then things are really broken
        pass

    return json.dumps(result)


if __name__ == '__main__':
    print(main())

