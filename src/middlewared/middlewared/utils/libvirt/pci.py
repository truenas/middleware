from middlewared.api.current import VMPCIDevice
from middlewared.service import ValidationErrors

from .delegate import DeviceDelegate
from .utils import ACTIVE_STATES


class PCIDelegate(DeviceDelegate):

    @property
    def schema_model(self):
        return VMPCIDevice

    def validate_middleware(
        self,
        device: dict,
        verrors: ValidationErrors,
        old: dict | None = None,
        vm_instance: dict | None = None,
        update: bool = True,
    ) -> None:
        if self.middleware.call_sync('system.is_ha_capable'):
            verrors.add('attribute.pptdev', 'HA capable systems do not support PCI passthrough')

        pptdev = device['attributes'].get('pptdev')
        if old and vm_instance and vm_instance['status']['state'] in ACTIVE_STATES and old[
            'attributes'
        ].get('pptdev') != pptdev:
            verrors.add(
                'attribute.pptdev',
                'Changing PCI device is not allowed while the VM is active.'
            )
