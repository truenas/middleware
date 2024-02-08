# Copyright (c) - iXsystems Inc.
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

import subprocess
import re

from pyudev import Context

from libsg3.ses import EnclosureDevice
from middlewared.service import Service
from middlewared.utils.functools_ import cache
from middlewared.plugins.truenas import PLATFORM_PREFIXES

from .ha_hardware import HA_HARDWARE

ENCLOSURES_DIR = '/sys/class/enclosure/'


class EnclosureDetectionService(Service):

    class Config:
        namespace = 'failover.enclosure'
        private = True

    @cache
    def detect(self):
        HARDWARE = NODE = 'MANUAL'
        dmi = self.middleware.call_sync('system.dmidecode_info')
        product = dmi['system-product-name']
        if not product:
            # no reason to continue since we've got no path forward
            return HARDWARE, NODE
        elif dmi['system-manufacturer'] == 'QEMU':
            serial = dmi['system-serial-number']
            if not serial.startswith('ha') and not serial.endswith(('_c1', '_c2')):
                # truenas is often installed in KVM so we need to check our specific
                # strings in DMI and bail out early here
                return HARDWARE, NODE
            else:
                HARDWARE = 'IXKVM'
                NODE = 'A' if serial[-1] == '1' else 'B'
                return HARDWARE, NODE
        elif product == 'BHYVE':
            # bhyve host configures a scsi_generic device that when sent an inquiry will
            # respond with a string that we use to determine the position of the node
            ctx = Context()
            for i in ctx.list_devices(subsystem='scsi_generic'):
                if (model := i.attributes.get('device/model')) is not None:
                    model = model.decode().strip() if isinstance(model, bytes) else model.strip()
                    if model == 'TrueNAS_A':
                        NODE = 'A'
                        HARDWARE = 'BHYVE'
                        break
                    elif model == 'TrueNAS_B':
                        NODE = 'B'
                        HARDWARE = 'BHYVE'
                        break

            return HARDWARE, NODE
        elif product.startswith('TRUENAS-F'):
            HARDWARE = 'LAJOLLA2'
            rv = subprocess.run(['ipmi-raw', '0', '3c', '0e'], stdout=subprocess.PIPE)
            if rv.stdout:
                # Viking info via VSS2249RQ Management Over IPMI document Section 5.5 page 15
                NODE = 'A' if rv.stdout.decode().strip()[-1] == '0' else 'B'

            return HARDWARE, NODE
        elif product.startswith('TRUENAS-H'):
            HARDWARE = 'SUBLIGHT'
            rv = subprocess.run(['ipmi-raw', '0', '6', '52', 'b', 'b2', '9', '0'], stdout=subprocess.PIPE)
            if rv.stdout:
                if (val := (int(rv.stdout.decode().strip()[-2:], base=16) & 1)) not in (0, 1):
                    # h-series is a unique platform so best to have messages like these for ease of
                    # troubleshooting if we're to hit something unexpected
                    self.logger.error('Unexpected value returned from MCU: %d (expected 0 or 1)', val)
                    return HARDWARE, NODE

                # (platform team has documentation if needed)
                # Bit 1 of 10th byte is 1 when "primary" controller from MCU 0xb2
                NODE = 'A' if val == 1 else 'B'

            return HARDWARE, NODE
        elif not product.startswith(PLATFORM_PREFIXES):
            # users run TrueNAS on all kinds of exotic hardware. Most of the time, the
            # exotic hardware doesn't respond to standards conforming requests. Furthermore,
            # the enclosure feature is specific to our HA appliances so no reason to continue
            # down this path.
            return HARDWARE, NODE

        for enc in self.middleware.call_sync('enclosure.list_ses_enclosures'):
            try:
                info = EnclosureDevice(enc).get_element_descriptor()
            except OSError:
                self.logger.warning('Error querying element descriptor page for %r', enc, exc_info=True)
                continue
            else:
                if re.search(HA_HARDWARE.ZSERIES_ENCLOSURE.value, info):
                    # Z-series Hardware (Echostream)
                    HARDWARE = 'ECHOSTREAM'
                    reg = re.search(HA_HARDWARE.ZSERIES_NODE.value, info)
                    NODE = reg.group(1)
                    if NODE:
                        break
                elif re.search(HA_HARDWARE.XSERIES_ENCLOSURE.value, info):
                    # X-series Hardware (PUMA)
                    HARDWARE = 'PUMA'

                    sas_addr = ''
                    with open(f'{ENCLOSURES_DIR}{enc.split("/")[-1]}/device/sas_address') as f:
                        # We need to get the SAS address of the SAS expander first
                        sas_addr = f.read().strip()

                    # We then cast the SES address (deduced from SES VPD pages)
                    # to an integer and subtract 1. Then cast it back to hexadecimal.
                    # We then compare if the SAS expander's SAS address
                    # is in the SAS expanders SES address
                    if (reg := re.search(HA_HARDWARE.XSERIES_NODEA.value, info)) is not None:
                        ses_addr = hex(int(reg.group(1), 16) - 1)
                        if ses_addr == sas_addr:
                            NODE = 'A'
                            break

                    if (reg := re.search(HA_HARDWARE.XSERIES_NODEB.value, info)) is not None:
                        ses_addr = hex(int(reg.group(1), 16) - 1)
                        if ses_addr == sas_addr:
                            NODE = 'B'
                            break
                elif (reg := re.search(HA_HARDWARE.MSERIES_ENCLOSURE.value, info)) is not None:
                    # M-series hardware (Echowarp)
                    HARDWARE = 'ECHOWARP'
                    if reg.group(2) == 'p':
                        NODE = 'A'
                        break
                    elif reg.group(2) == 's':
                        NODE = 'B'
                        break

        return HARDWARE, NODE
