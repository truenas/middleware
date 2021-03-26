import subprocess

from middlewared.service import CallError
from middlewared.schema import Dict, Str
from middlewared.utils import osc

from .device import Device
from .utils import create_element, LIBVIRT_URI


class PCI(Device):

    schema = Dict(
        'attributes',
        Str('pptdev', required=True, empty=False),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if osc.IS_FREEBSD:
            self.init_ppt_map()

    def detach_device(self):
        cp = subprocess.Popen(['virsh', '-c', LIBVIRT_URI, 'nodedev-detach', self.passthru_device()])
        stderr = cp.communicate()[1]
        if cp.returncode:
            raise CallError(f'Unable to detach {self.passthru_device()} PCI device: {stderr.decode()}')

    def reattach_device(self):
        cp = subprocess.Popen(['virsh', '-c', LIBVIRT_URI, 'nodedev-reattach', self.passthru_device()])
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

    def init_ppt_map(self):
        iommu_enabled = self.middleware.call_sync('vm.device.iommu_enabled')
        pptdevs = self.middleware.call_sync('vm.device.pptdev_choices')
        pptdev = self.data['attributes'].get('pptdev')
        self.ppt_map = {
            'host_bsf': list(map(int, pptdev.split('/'))) if pptdev in pptdevs and iommu_enabled else None,
            'guest_bsf': None
        }

    def xml_freebsd(self, *args, **kwargs):
        # If passthru is performed by means of additional command-line arguments
        # to the bhyve process using the <bhyve:commandline> element under domain,
        # the xml is TYPICALLY not needed. An EXCEPTION is when there are devices
        # for which the pci address is not under the control of and set by
        # middleware and generation of the xml can reduce the risk for conflicts.
        # It appears that when assigning addresses to other devices libvirt avoids
        # the pci address provided in the xml also when libvirt does not (fully)
        # support hostdev for bhyve.
        host_bsf = self.ppt_map['host_bsf']
        guest_bsf = self.ppt_map['guest_bsf']

        return create_element(
            'hostdev', mode='subsystem', type='pci', managed='no', attribute_dict={
                'children': [
                    create_element(
                        'source', attribute_dict={
                            'children': [
                                create_element(
                                    'address', domain='0x0000', bus='0x{:04x}'.format(host_bsf[0]),
                                    slot='0x{:04x}'.format(host_bsf[1]), function='0x{:04x}'.format(host_bsf[2])
                                ),
                            ]
                        }
                    ),
                    create_element(
                        'address', type='pci', domain='0x0000', bus='0x{:04x}'.format(guest_bsf[0]),
                        slot='0x{:04x}'.format(guest_bsf[1]), function='0x{:04x}'.format(guest_bsf[2])
                    ),
                ]
            }
        ) if guest_bsf is not None else None

    def hypervisor_args_freebsd(self, *args, **kwargs):
        # Unless libvirt supports hostdev for bhyve, we need to pass pci devices
        # through to guest by means of additional command-line arguments to the
        # bhyve process using the <bhyve:commandline> element under domain.
        return '-s {g[1]}:{g[2]},passthru,{h[0]}/{h[1]}/{h[2]}'.format(
            g=self.ppt_map['guest_bsf'], h=self.ppt_map['host_bsf']
        ) if self.ppt_map['guest_bsf'] is not None else None
