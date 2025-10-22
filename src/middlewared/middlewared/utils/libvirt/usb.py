from middlewared.service_exception import ValidationErrors

from .delegate import DeviceDelegate


USB_CONTROLLER_CHOICES = [
    'piix3-uhci', 'piix4-uhci', 'ehci', 'ich9-ehci1',
    'vt82c686b-uhci', 'pci-ohci', 'nec-xhci', 'qemu-xhci',
]


class USBDelegate(DeviceDelegate):

    def validate_middleware(
        self,
        device: dict,
        verrors: ValidationErrors,
        old: dict | None = None,
        instance: dict | None = None,
        update: bool = True,
    ) -> None:
        if self.middleware.call_sync('system.is_ha_capable'):
            verrors.add('attributes.usb', 'HA capable systems do not support USB passthrough.')
