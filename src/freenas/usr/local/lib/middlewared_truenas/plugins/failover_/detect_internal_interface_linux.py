# Copyright (c) - iXsystems Inc.
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

import glob

from middlewared.service import private, Service


ZSERIES_PCI_ID = 'PCI_ID=8086:10D3'
ZSERIES_PCI_SUBSYS_ID = 'PCI_SUBSYS_ID=8086:A01F'
INTERFACE_GLOB = '/sys/class/net/*/device/uevent'


class InternalInterfaceDetectionService(Service):

    class Config:
        namespace = 'failover.internal_interface'

    @private
    def detect(self):

        hardware = self.middleware.call_sync(
            'failover.hardware'
        )

        # Detect Z-series heartbeat interface
        if hardware == 'ECHOSTREAM':
            for i in glob.iglob(INTERFACE_GLOB):
                with open(i, 'r') as f:
                    data = f.read()

                    if ZSERIES_PCI_ID and ZSERIES_PCI_SUBSYS_ID in data:
                        return [i.split('/')[4].strip()]

        # Detect X-series and M-series heartbeat interface
        # TODO: Fix this
        if hardware in ('PUMA', 'ECHOWARP'):
            pass

        return []
