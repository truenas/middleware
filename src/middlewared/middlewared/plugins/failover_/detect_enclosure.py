# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

import pathlib
import subprocess

from pyudev import Context

from ixhardware import PLATFORM_PREFIXES

from middlewared.service import Service
from middlewared.utils.functools_ import cache

from middlewared.plugins.enclosure_.ses_enclosures2 import get_ses_enclosures


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
        elif product.startswith('TRUENAS-V'):
            # HARDWARE depends on whether V1XX or V2XX
            match product[9]:
                case '1':
                    HARDWARE = 'LUDICROUS'
                case '2':
                    HARDWARE = 'PLAID'
                case _:
                    return HARDWARE, NODE
            for s in get_ses_enclosures(False):
                if s.vendor == 'ECStream':
                    if s.product == '4IXGA-NTBp':
                        NODE = 'A'
                        break
                    elif s.product == '4IXGA-NTBs':
                        NODE = 'B'
                        break
            return HARDWARE, NODE
        elif not product.startswith(PLATFORM_PREFIXES):
            # users run TrueNAS on all kinds of exotic hardware. Most of the time, the
            # exotic hardware doesn't respond to standards conforming requests. Furthermore,
            # the enclosure feature is specific to our HA appliances so no reason to continue
            # down this path.
            return HARDWARE, NODE

        for enc in get_ses_enclosures(False):
            if enc.is_mseries:
                HARDWARE = 'ECHOWARP'
                if enc.product == '4024Sp':
                    return HARDWARE, 'A'
                elif enc.product == '4024Ss':
                    return HARDWARE, 'B'
            elif enc.is_xseries:
                HARDWARE = 'PUMA'
                esce = enc.elements.get('Enclosure Services Controller Electronics', {})
                for i in esce.values():
                    if i['descriptor'].startswith(('ESCE A_', 'ESCE B_')):
                        node = i['descriptor'][5]
                        # We then cast the SES address (deduced from SES VPD pages)
                        # to an integer and subtract 1. Then cast it back to hexadecimal.
                        # We then compare if the SAS expander's SAS address is the same
                        # as the SAS expanders SES address.
                        ses_addr = hex(int(i['descriptor'][7:].strip(), 16) - 1)
                        sas_addr = pathlib.Path(
                            f'/sys/class/enclosure/{enc.pci}/device/sas_address'
                        ).read_text().strip()
                        if ses_addr == sas_addr:
                            return HARDWARE, node

        return HARDWARE, NODE
