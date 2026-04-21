from typing import Any

from middlewared.service import ValidationErrors

from .delegate import DeviceDelegate
from .utils import ACTIVE_STATES, device_uniqueness_check


class PCIDelegate(DeviceDelegate):

    def validate_middleware(
        self,
        device: dict[str, Any],
        verrors: ValidationErrors,
        old: dict[str, Any] | None = None,
        instance: dict[str, Any] | None = None,
        update: bool = True,
    ) -> None:
        if self.middleware.call_sync('system.is_ha_capable'):
            verrors.add('attribute.pptdev', 'HA capable systems do not support PCI passthrough')

        pptdev = device['attributes'].get('pptdev')
        if old and instance and instance['status']['state'] in ACTIVE_STATES and old[
            'attributes'
        ].get('pptdev') != pptdev:
            verrors.add(
                'attribute.pptdev',
                'Changing PCI device is not allowed while the VM is active.'
            )

        if instance is not None and not device_uniqueness_check(device, instance, 'PCI'):
            verrors.add(
                'attributes.pptdev',
                f'{instance["name"]} already has PCI device {pptdev!r} configured'
            )
