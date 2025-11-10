import re

from middlewared.api import api_method
from middlewared.api.current import VMGuestArchitectureAndMachineChoicesArgs, VMGuestArchitectureAndMachineChoicesResult
from middlewared.service import private, Service
from middlewared.utils import run


RE_MACHINE_TYPE_CHOICES = re.compile(r'^\s*(?!none\s)(\S+)(?=\s{2,})', flags=re.M)


class VMService(Service):

    CAPABILITIES = None

    @private
    async def update_capabilities_cache(self):
        """
        Query QEMU binaries directly to get supported architectures and machine types.
        """
        supported_archs = {}

        cp = await run(['/usr/bin/qemu-system-x86_64', '-machine', 'help'], check=False, encoding='utf-8')
        if cp.returncode:
            self.logger.warning(f'Failed to query machine types for x86_64: {cp.stderr}')
        else:
            if machine_types := RE_MACHINE_TYPE_CHOICES.findall(cp.stdout):
                supported_archs['x86_64'] = machine_types

        cp = await run(['/usr/bin/qemu-system-i386', '-machine', 'help'], check=False, encoding='utf-8')
        if cp.returncode:
            self.logger.warning(f'Failed to query machine types for i686: {cp.stderr}')
        else:
            if machine_types := RE_MACHINE_TYPE_CHOICES.findall(cp.stdout):
                supported_archs['i686'] = machine_types

        self.CAPABILITIES = supported_archs

    @api_method(VMGuestArchitectureAndMachineChoicesArgs, VMGuestArchitectureAndMachineChoicesResult, roles=['VM_READ'])
    async def guest_architecture_and_machine_choices(self):
        """
        Retrieve choices for supported guest architecture types and machine choices.

        Keys in the response would be supported guest architecture(s) on the host and their respective values would
        be supported machine type(s) for the specific architecture on the host.
        """
        if not self.CAPABILITIES:
            await self.middleware.call('vm.update_capabilities_cache')
        return self.CAPABILITIES
