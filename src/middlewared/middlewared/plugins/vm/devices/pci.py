import subprocess

from middlewared.service import CallError
from middlewared.schema import Dict, Str

from .device import Device
from .utils import create_element, LIBVIRT_URI


class PCI(Device):

    schema = Dict(
        'attributes',
        Str('pptdev', required=True, empty=False),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def detach_device(self):
        cp = subprocess.Popen(
            ['virsh', '-c', LIBVIRT_URI, 'nodedev-detach', self.passthru_device()],
            stderr=subprocess.PIPE, stdout=subprocess.DEVNULL
        )
        stderr = cp.communicate()[1]
        if cp.returncode:
            raise CallError(f'Unable to detach {self.passthru_device()} PCI device: {stderr.decode()}')

    def reattach_device(self):
        cp = subprocess.Popen(
            ['virsh', '-c', LIBVIRT_URI, 'nodedev-reattach', self.passthru_device()],
            stderr=subprocess.PIPE, stdout=subprocess.DEVNULL
        )
        stderr = cp.communicate()[1]
        if cp.returncode:
            raise CallError(f'Unable to re-attach {self.passthru_device()} PCI device: {stderr.decode()}')

    def pre_start_vm_device_setup_linux(self, *args, **kwargs):
        device = self.get_details()
        if not device['error'] and not device['available']:
            self.detach_device()

    def is_available(self):
        return self.get_details()['available']

    def identity(self):
        return str(self.passthru_device())

    def passthru_device(self):
        return str(self.data['attributes']['pptdev'])

    def get_vms_using_device(self):
        devs = self.middleware.call_sync(
            'vm.device.query', [['attributes.pptdev', '=', self.passthru_device()], ['dtype', '=', 'PCI']]
        )
        return self.middleware.call_sync('vm.query', [['id', 'in', [dev['vm'] for dev in devs]]])

    def safe_to_reattach(self):
        return all(vm['status']['state'] != 'RUNNING' for vm in self.get_vms_using_device())

    def post_stop_vm_linux(self, *args, **kwargs):
        if self.safe_to_reattach():
            try:
                self.reattach_device()
            except CallError:
                self.middleware.logger.error('Failed to re-attach %s device', self.passthru_device(), exc_info=True)

    def get_details(self):
        return self.middleware.call_sync('vm.device.passthrough_device', self.passthru_device())

    def xml_linux(self, *args, **kwargs):
        address_info = {
            k: hex(int(v)) for k, v in self.get_details()['capability'].items()
            if k in ('domain', 'bus', 'slot', 'function')
        }

        return create_element(
            'hostdev', mode='subsystem', type='pci', managed='yes', attribute_dict={
                'children': [
                    create_element('source', attribute_dict={'children': [create_element('address', **address_info)]}),
                ]
            }
        )
