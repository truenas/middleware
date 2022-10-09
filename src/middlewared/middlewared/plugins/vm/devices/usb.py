from middlewared.schema import Dict, Str

from .device import Device
from .utils import create_element


class USB(Device):

    schema = Dict(
        'attributes',
        Dict(
            'usb',
            Str('vendor_id', empty=False),
            Str('product_id', empty=False),
            default=None,
        ),
        Str('device', empty=False, null=True),
    )

    @property
    def usb_device(self):
        return self.data['attributes']['device']

    @property
    def usb_details(self):
        return self.data['attributes']['usb']

    def identity(self):
        return self.usb_device

    def get_vms_using_device(self):
        devs = self.middleware.call_sync(
            'vm.device.query', [['attributes.device', '=', self.usb_device], ['dtype', '=', 'USB']]
        )
        return self.middleware.call_sync('vm.query', [['id', 'in', [dev['vm'] for dev in devs]]])

    def get_details(self):
        usb_device = self.usb_device
        if not usb_device and self.usb_details:
            usb_device = self.middleware.call_sync('vm.device.get_usb_port_from_usb_details', self.usb_details)
        if usb_device:
            return self.middleware.call_sync('vm.device.usb_passthrough_device', usb_device)
        else:
            return self.middleware.call_sync('vm.device.usb_passthrough_device', str(usb_device))

    def is_available(self):
        return self.get_details()['available']

    def xml_linux(self, *args, **kwargs):
        details = self.get_details()['capability']
        device_xml = create_element(
            'hostdev', mode='subsystem', type='usb', managed='yes', attribute_dict={
                'children': [
                    create_element('source', attribute_dict={'children': [
                        create_element('vendor', id=details['vendor_id']),
                        create_element('product', id=details['product_id']),
                        create_element('address', bus=details['bus'], device=details['device']),
                    ]}),
                ]
            }
        )
        return device_xml

    def _validate(self, device, verrors, old=None, vm_instance=None, update=True):
        if device['attributes']['device'] and device['attributes']['usb']:
            verrors.add(
                'attributes.usb',
                'Either device must be specified or USB details but not both'
            )

        if verrors:
            return

        if device['attributes']['device']:
            self._validate_usb_port(device, verrors)
        else:
            self._validate_usb_details(device, verrors)

    def _validate_usb_details(self, device, verrors):
        usb_details = device['attributes']['usb']
        for k in filter(lambda k: not usb_details.get(k), ('product_id', 'vendor_id')):
            verrors.add(
                f'attribute.usb.{k}',
                'This is required'
            )
        if verrors:
            return

        if not self.middleware.call_sync('vm.device.get_usb_port_from_usb_details', usb_details):
            verrors.add(
                f'attributes.usb',
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
