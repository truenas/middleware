from middlewared.schema import Dict, Str
from middlewared.validators import Match

from .device import Device
from .utils import create_element


class PCI(Device):

    schema = Dict(
        'attributes',
        Str('pptdev', required=True, validators=[Match(r'([0-9]+/){2}[0-9]+')]),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.init_ppt_map()

    def init_ppt_map(self):
        iommu_type = self.middleware.call_sync('vm.device.get_iommu_type')
        pptdevs = self.middleware.call_sync('vm.device.pptdev_choices')
        pptdev = self.data['attributes'].get('pptdev')
        self.ppt_map = {
            'host_bsf': list(map(int, pptdev.split('/'))) if pptdev in pptdevs and iommu_type else None,
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

    def bhyve_args(self, *args, **kwargs):
        # Unless libvirt supports hostdev for bhyve, we need to pass pci devices
        # through to guest by means of additional command-line arguments to the
        # bhyve process using the <bhyve:commandline> element under domain.
        return '-s {g[1]}:{g[2]},passthru,{h[0]}/{h[1]}/{h[2]}'.format(
            g=self.ppt_map['guest_bsf'], h=self.ppt_map['host_bsf']
        ) if self.ppt_map['guest_bsf'] is not None else None
