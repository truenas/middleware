import subprocess
import re

from pyudev import Context

from middlewared.service import Service
from middlewared.utils.functools import cache
from .ha_hardware import HA_HARDWARE

ENCLOSURES_DIR = '/sys/class/enclosure/'


class EnclosureDetectionService(Service):

    class Config:
        namespace = 'failover.enclosure'
        private = True

    HARDWARE = NODE = 'MANUAL'

    @cache
    def detect(self):

        # first check to see if this is a BHYVE instance
        manufacturer = self.middleware.call_sync('system.dmidecode_info')['system-product-name']
        if manufacturer == 'BHYVE':
            # bhyve host configures a scsi_generic device that when sent an inquiry will
            # respond with a string that we use to determine the position of the node
            ctx = Context()
            for i in ctx.list_devices(subsystem='scsi_generic'):
                if (model := i.attributes.get('device/model')) is not None:
                    model = model.decode().strip() if isinstance(model, bytes) else model.strip()
                    if model == 'TrueNAS_A':
                        self.NODE = 'A'
                        self.HARDWARE = manufacturer
                        break
                    elif model == 'TrueNAS_B':
                        self.NODE = 'B'
                        self.HARDWARE = manufacturer
                        break

            return self.HARDWARE, self.NODE

        # Gather the PCI address for all enclosurers
        # detected by the kernel
        enclosures = self.middleware.call_sync("enclosure.list_ses_enclosures")
        if not enclosures:
            # No enclosures detected
            return self.HARDWARE, self.NODE

        for enc in enclosures:
            proc = subprocess.run(
                ['/usr/bin/sg_ses', '-p', 'ed', enc],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            if proc.stdout:
                info = proc.stdout.decode(errors='ignore', encoding='utf8')

                # Identify the Z-series Hardware (Echostream)
                if re.search(HA_HARDWARE.ZSERIES_ENCLOSURE.value, info):
                    self.HARDWARE = 'ECHOSTREAM'
                    reg = re.search(HA_HARDWARE.ZSERIES_NODE.value, info)
                    self.NODE = reg.group(1)
                    if self.NODE:
                        break

                # Identify the X-series Hardware (PUMA)
                # TODO: Verify this works on X-series Hardware
                elif re.search(HA_HARDWARE.XSERIES_ENCLOSURE.value, info):
                    self.HARDWARE = 'PUMA'

                    # We need to get the SAS address of the SAS expander first
                    sas_addr_file = ENCLOSURES_DIR + enc.split('/dev/bsg/')[-1] + '/id'
                    with open(sas_addr_file, 'r') as f:
                        sas_addr = f.read().strip()

                    # We then cast the SES address (deduced from SES VPD pages)
                    # to an integer and subtract 1. Then cast it back to hexadecimal.
                    # We then compare if the SAS expander's SAS address
                    # is in the SAS expanders SES address
                    reg = re.search(HA_HARDWARE.XSERIES_NODEA.value, info)
                    if reg:
                        ses_addr = hex(int(reg.group(1), 16) - 1)
                        if ses_addr in sas_addr:
                            self.NODE = 'A'
                            break

                    reg = re.search(HA_HARDWARE.XSERIES_NODEB.value, info)
                    if reg:
                        ses_addr = hex(int(reg.group(1), 16) - 1)
                        if ses_addr in sas_addr:
                            self.NODE = 'B'
                            break

                # Identify the M-series hardware (Echowarp)
                else:
                    reg = re.search(HA_HARDWARE.MSERIES_ENCLOSURE.value, info)
                    if reg:
                        self.HARDWARE = 'ECHOWARP'

                        # Identify M-series A slot in chassis
                        if reg.group(2) == 'p':
                            self.NODE = 'A'
                            break

                        # Identify M-series B slot in chassis
                        if reg.group(2) == 's':
                            self.NODE = 'B'
                            break

        return self.HARDWARE, self.NODE
