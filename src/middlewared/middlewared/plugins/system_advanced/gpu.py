from middlewared.schema import accepts, Dict, List, returns, Str
from middlewared.service import private, Service, ValidationErrors
from middlewared.utils.gpu import get_gpus


class SystemAdvancedService(Service):

    class Config:
        namespace = 'system.advanced'
        cli_namespace = 'system.advanced'

    @accepts(roles=['SYSTEM_ADVANCED_READ'])
    @returns(Dict(additional_attrs=True))
    def get_gpu_pci_choices(self):
        """
        This endpoint gives all the gpu pci ids/slots that can be isolated.
        """
        configured_value = self.middleware.call_sync('system.advanced.config')['isolated_gpu_pci_ids']
        gpus = {
            f'{gpu["description"]} [{gpu["addr"]["pci_slot"]}]': gpu['addr']['pci_slot']
            for gpu in get_gpus() if not gpu['uses_system_critical_devices']
        }
        for slot in filter(lambda gpu: gpu not in gpus.values(), configured_value):
            gpus[f'Unknown {slot!r} slot'] = slot

        return gpus

    @accepts(List('isolated_gpu_pci_ids', items=[Str('pci_id')], required=True), roles=['SYSTEM_ADVANCED_WRITE'])
    @returns()
    async def update_gpu_pci_ids(self, isolated_gpu_pci_ids):
        """
        `isolated_gpu_pci_ids` is a list of PCI ids which are isolated from host system.
        """
        verrors = ValidationErrors()
        if isolated_gpu_pci_ids:
            verrors = await self.validate_gpu_pci_ids(isolated_gpu_pci_ids, verrors, 'gpu_settings')

        if await self.middleware.call('system.is_ha_capable') and isolated_gpu_pci_ids:
            verrors.add(
                'gpu_settings.isolated_gpu_pci_ids',
                'HA capable systems do not support PCI passthrough'
            )

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
