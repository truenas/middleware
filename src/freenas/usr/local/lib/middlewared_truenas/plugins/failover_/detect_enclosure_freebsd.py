# Copyright (c) - iXsystems Inc.
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

import subprocess
import re
import os

from middlewared.service import private, Service
from ..failover import HA_HARDWARE


class EnclosureDetectionService(Service):

    class Config:
        namespace = 'failover.enclosure'

    HARDWARE = NODE = 'MANUAL'

    @private
    def detect(self):

        # First check if this is a BHYVE HA instance, or IXKVM HA instance
        dmi = self.middleware.call_sync('system.dmidecode_info')
        manufacturer = dmi['system-product-name']

        if manufacturer == 'BHYVE':
            devlist = subprocess.run(
                ['/sbin/camcontrol', 'devlist'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            if devlist.stdout:
                devlist = devlist.stdout.decode(errors='ignore', encoding='utf8').strip()

                # We only return BHYVE as the type of hardware
                # when this is specifically being run on a
                # BHYVE HA instance that iXsystems uses internally.
                ids = ['TrueNAS_A', 'TrueNAS_B']
                if any(x in devlist for x in ids):
                    self.HARDWARE = manufacturer

                    if 'TrueNAS_A' in devlist:
                        self.NODE = 'A'
                    elif 'TrueNAS_B' in devlist:
                        self.NODE = 'B'

                    return self.HARDWARE, self.NODE
        elif dmi['system-manufacturer'] == 'QEMU':
            serial = dmi['system-serial-number']
            if not serial.startswith('ha') and not serial.endswith(('_c1', '_c2')):
                # truenas is often installed in KVM so we need to check our specific
                # strings in DMI and bail out early here
                return self.HARDWARE, self.NODE
            else:
                self.HARDWARE = 'IXKVM'
                self.NODE = 'A' if serial[-1] == '1' else 'B'
                return self.HARDWARE, self.NODE

        # We're not BHYVE or IXKVM if we get here so identify the
        # hardware platform accordingly.
        enclosures = [
            '/dev/' + i for i in os.listdir('/dev')
            if i.startswith('ses')
        ]

        for enclosure in enclosures:
            enc = subprocess.run(
                ['/usr/sbin/getencstat', '-V', enclosure],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            if enc.stdout:
                enc = enc.stdout.decode(errors='ignore', encoding='utf8').strip()

                # Identify the Z-series Hardware (Echostream)
                if re.search(HA_HARDWARE.ZSERIES_ENCLOSURE.value, enc):
                    self.HARDWARE = 'ECHOSTREAM'

                    # Identify Z-series A or B slot in chassis
                    reg = re.search(HA_HARDWARE.ZSERIES_NODE.value, enc)
                    self.NODE = reg.group(1)
                    if self.NODE:
                        break

                # Identify the X-series Hardware (PUMA)
                elif re.search(HA_HARDWARE.XSERIES_ENCLOSURE.value, enc):
                    self.HARDWARE = 'PUMA'

                    # Identify controller by comparing addresses
                    # from SES and SMP.
                    # There is no exact match, but allocation of
                    # the SAS addresses seem sequential.
                    phylist = subprocess.run(
                        ['/sbin/camcontrol', 'smpphylist', enclosure, '-q'],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )

                    if phylist.stdout:
                        phylist = phylist.stdout.decode(errors='ignore', encoding='utf8').strip()

                        # Identify X-series A slot in chassis
                        reg = re.search(HA_HARDWARE.XSERIES_NODEA.value, enc)
                        if reg:
                            addr = f'0x{(int(reg.group(1), 16) - 1):016x}'
                            if addr in phylist:
                                self.NODE = 'A'
                                break

                        # Identify X-series B slot in chassis
                        reg = re.search(HA_HARDWARE.XSERIES_NODEB.value, enc)
                        if reg:
                            addr = f'0x{(int(reg.group(1), 16) - 1):016x}'
                            if addr in phylist:
                                self.NODE = 'B'
                                break

                # Identify the M-series Hardware (Echowarp)
                else:

                    reg = re.search(HA_HARDWARE.MSERIES_ENCLOSURE.value, enc)
                    if reg:
                        self.HARDWARE = 'ECHOWARP'

                        # Identify M-series A slot in chassis
                        if reg.group(2) == 'p':
                            self.NODE = 'A'
                            break

                        # Identify M-series B slot in chassis
                        elif reg.group(2) == 's':
                            self.NODE = 'B'
                            break

        return self.HARDWARE, self.NODE
