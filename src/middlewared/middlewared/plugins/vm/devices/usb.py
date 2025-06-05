from middlewared.api.current import VMUSBDevice
from middlewared.schema import Dict

from .pci import PCIBase
from .utils import create_element


USB_CONTROLLER_CHOICES = [
    'piix3-uhci', 'piix4-uhci', 'ehci', 'ich9-ehci1',
    'vt82c686b-uhci', 'pci-ohci', 'nec-xhci', 'qemu-xhci',
]


class USB(PCIBase):

    schema = Dict(
        'attributes',
    )
    schema_model = VMUSBDevice

    @property
    def usb_device(self):
        return self.data['attributes']['device']

    @property
    def controller_type(self):
        return self.data['attributes']['controller_type']

    @property
    def usb_details(self):
        return self.data['attributes']['usb']

    def identity(self):
        return self.usb_device or f'{self.usb_details["product_id"]}--{self.usb_details["vendor_id"]}'

    def vm_device_filters(self):
        if self.usb_device:
            return [['attributes.device', '=', self.usb_device], ['dtype', '=', 'USB']]
        else:
            return [['attributes.usb', '=', self.usb_details], ['dtype', '=', 'USB']]

    def get_details(self):
        usb_device = self.usb_device
        if not usb_device and self.usb_details:
            usb_device = self.middleware.call_sync('vm.device.get_usb_port_from_usb_details', self.usb_details)
        if usb_device:
            return self.middleware.call_sync('vm.device.usb_passthrough_device', usb_device)
        else:
            return {
                **self.middleware.call_sync('vm.device.get_basic_usb_passthrough_device_data'),
                'error': 'Could not find matching device as no usb device has been specified',
            }

    def xml(self, *args, **kwargs):
        controller_mapping = kwargs.pop('controller_mapping')
        details = self.get_details()['capability']
        if self.is_available():
            return create_element(
                'hostdev', mode='subsystem', type='usb', managed='yes', attribute_dict={
                    'children': [
                        create_element('source', attribute_dict={'children': [
                            create_element('vendor', id=details['vendor_id']),
                            create_element('product', id=details['product_id']),
                            create_element('address', bus=details['bus'], device=details['device']),
                        ]}),
                        create_element('address', type='usb', bus=str(controller_mapping[self.controller_type])),
                    ]
                }
            )
        else:
            return []

    def _validate(self, device, verrors, old=None, vm_instance=None, update=True):
        if device['attributes']['device'] and device['attributes']['usb']:
            verrors.add(
                'attributes.usb',
                'Either device must be specified or USB details but not both'
            )
        elif not device['attributes']['device'] and not device['attributes']['usb']:
            verrors.add(
                'attributes.device',
                'Either device or attributes.usb must be specified'
            )

        if self.middleware.call_sync('system.is_ha_capable'):
            verrors.add('attributes.usb', 'HA capable systems do not support USB passthrough.')

        if verrors:
            return

        if device['attributes']['device']:
            self._validate_usb_port(device, verrors)
        else:
            self._validate_usb_details(device, verrors)

    def _validate_usb_details(self, device, verrors):
        usb_details = device['attributes']['usb']
        if not self.middleware.call_sync('vm.device.get_usb_port_from_usb_details', usb_details):
            verrors.add(
                'attributes.usb',
                'Unable to locate USB, please confirm its present in a USB port'
            )

    def _validate_usb_port(self, device, verrors):
        usb_device = device['attributes']['device']
        device_details = self.middleware.call_sync('vm.device.usb_passthrough_device', usb_device)
        if device_details.get('error'):
            verrors.add(
                'attribute.device',
                f'Not a valid choice. The device is not available for USB passthrough: {device_details["error"]}'
            )
