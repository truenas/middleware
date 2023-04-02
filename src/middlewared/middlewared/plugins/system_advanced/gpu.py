from middlewared.schema import accepts, List, returns, Str
from middlewared.service import private, Service, ValidationErrors


class SystemAdvancedService(Service):

    class Config:
        namespace = 'system.advanced'
        cli_namespace = 'system.advanced'

    @accepts(List('isolated_gpu_pci_ids', items=[Str('pci_id')], required=True))
    @returns()
    async def update_gpu_pci_ids(self, isolated_gpu_pci_ids):
        """
        `isolated_gpu_pci_ids` is a list of PCI ids which are isolated from host system.
        """
        verrors = ValidationErrors()
        if isolated_gpu_pci_ids:
            verrors = await self.validate_gpu_pci_ids(isolated_gpu_pci_ids, verrors, 'gpu_settings')

        verrors.check()

        await self.middleware.call(
            'datastore.update',
            'system.advanced',
            (await self.middleware.call('system.advanced.config'))['id'],
            {'isolated_gpu_pci_ids': isolated_gpu_pci_ids},
            {'prefix': 'adv_'}
        )
        await self.middleware.call('boot.update_initramfs')

    @private
    async def validate_gpu_pci_ids(self, isolated_gpu_pci_ids, verrors, schema):
        available = set()
        critical_gpus = set()
        for gpu in await self.middleware.call('device.get_gpus'):
            available.add(gpu['addr']['pci_slot'])
            if gpu['uses_system_critical_devices']:
                critical_gpus.add(gpu['addr']['pci_slot'])

        provided = set(isolated_gpu_pci_ids)
        not_available = provided - available
        cannot_isolate = provided & critical_gpus
        if not_available:
            verrors.add(
                f'{schema}.isolated_gpu_pci_ids',
                f'{", ".join(not_available)} GPU pci slot(s) are not available or a GPU is not configured.'
            )

        if cannot_isolate:
            verrors.add(
                f'{schema}.isolated_gpu_pci_ids',
                f'{", ".join(cannot_isolate)} GPU pci slot(s) consists of devices '
                'which cannot be isolated from host.'
            )

        if len(available - provided) < 1:
            verrors.add(
                f'{schema}.isolated_gpu_pci_ids',
                'A minimum of 1 GPU is required for the host to ensure it functions as desired.'
            )

        return verrors
