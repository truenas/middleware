from collections import defaultdict
from xml.etree import ElementTree as etree

from middlewared.api import api_method
from middlewared.api.current import VMGuestArchitectureMachineChoicesArgs, VMGuestArchitectureMachineChoicesResult
from middlewared.service import private, Service

from .connection import LibvirtConnectionMixin


class VMService(Service, LibvirtConnectionMixin):

    CAPABILITIES = None

    @private
    def update_capabilities_cache(self):
        self._check_setup_connection()
        xml = etree.fromstring(self.LIBVIRT_CONNECTION.getCapabilities())
        supported_archs = defaultdict(list)
        for guest in xml.findall('guest'):
            arch = guest.find('arch')
            if not arch or not arch.get('name'):
                continue
            arch_name = arch.get('name')

            for machine_type in filter(lambda m: m.text, arch.findall('machine')):
                supported_archs[arch_name].append(machine_type.text)

        self.CAPABILITIES = supported_archs

    @api_method(VMGuestArchitectureMachineChoicesArgs, VMGuestArchitectureMachineChoicesResult, roles=['VM_READ'])
    async def guest_architecture_and_machine_choices(self):
        """
        Retrieve choices for supported guest architecture types and machine choices.

        Keys in the response would be supported guest architecture(s) on the host and their respective values would
        be supported machine type(s) for the specific architecture on the host.
        """
        if not self.CAPABILITIES:
            await self.middleware.call('vm.update_capabilities_cache')
        return self.CAPABILITIES
