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
        if self.middleware.call_sync('system.dmidecode_info')['system-product-name'] == 'BHYVE':
            # bhyve host configures a scsi_generic device that when sent an inquiry will
            # respond with a string that we use to determine the position of the node
            ctx = Context()
            for i in ctx.list_devices(subsystem='scsi_generic'):
                if (model := i.attributes.get('device/model')) is not None:
                    model = model.decode().strip() if isinstance(model, bytes) else model.strip()
                    if model == 'TrueNAS_A':
                        self.NODE = 'A'
                        self.HARDWARE = 'BHYVE'
                        break
                    elif model == 'TrueNAS_B':
                        self.NODE = 'B'
                        self.HARDWARE = 'BHYVE'
                        break

            return self.HARDWARE, self.NODE

        for enc in self.middleware.call_sync("enclosure.list_ses_enclosures"):
            proc = subprocess.run(
                ['/usr/bin/sg_ses', '-p', 'ed', enc],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if proc.stdout:
                info = proc.stdout.decode(errors='ignore', encoding='utf8')

                if re.search(HA_HARDWARE.ZSERIES_ENCLOSURE.value, info):
                    # Z-series Hardware (Echostream)
                    self.HARDWARE = 'ECHOSTREAM'
                    reg = re.search(HA_HARDWARE.ZSERIES_NODE.value, info)
                    self.NODE = reg.group(1)
                    if self.NODE:
                        break
                elif re.search(HA_HARDWARE.XSERIES_ENCLOSURE.value, info):
                    # X-series Hardware (PUMA)
                    self.HARDWARE = 'PUMA'

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
                            self.NODE = 'A'
                            break
                    elif (reg := re.search(HA_HARDWARE.XSERIES_NODEB.value, info)) is not None:
                        ses_addr = hex(int(reg.group(1), 16) - 1)
                        if ses_addr == sas_addr:
                            self.NODE = 'B'
                            break
                elif (reg := re.search(HA_HARDWARE.MSERIES_ENCLOSURE.value, info)) is not None:
                    # M-series hardware (Echowarp)
                    self.HARDWARE = 'ECHOWARP'
                    if reg.group(2) == 'p':
                        self.NODE = 'A'
                        break
                    elif reg.group(2) == 's':
                        self.NODE = 'B'
                        break

        return self.HARDWARE, self.NODE
