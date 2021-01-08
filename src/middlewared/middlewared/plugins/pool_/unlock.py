from middlewared.schema import Str
from middlewared.service import accepts, private, Service
from middlewared.utils import osc


class PoolDatasetService(Service):

    class Config:
        namespace = 'pool.dataset'
        event_send = False

    @accepts(Str('dataset'))
    async def unlock_services_restart_choices(self, dataset):
        """
        Get a mapping of services identifiers and labels that can be restart on dataset unlock.
        """
        services = {
            'afp': 'AFP',
            'cifs': 'SMB',
            'ftp': 'FTP',
            'iscsitarget': 'iSCSI',
            'nfs': 'NFS',
            'webdav': 'WebDAV',
        }

        result = {}
        for k, v in services.items():
            service = await self.middleware.call('service.query', [['service', '=', k]], {'get': True})
            if service['enable'] or service['state'] == 'RUNNING':
                result[k] = v

        if osc.IS_FREEBSD:
            try:
                activated_pool = await self.middleware.call('jail.get_activated_pool')
            except Exception:
                activated_pool = None

            # If iocage is not activated yet, there is a chance that this pool might have it activated there
            if activated_pool is None:
                result['jails'] = 'Jails/Plugins'

        if await self.unlock_restarted_vms(dataset):
            result['vms'] = 'Virtual Machines'

        return result

    @private
    async def unlock_restarted_vms(self, dataset_name):
        result = []
        for vm in await self.middleware.call('vm.query', [('autostart', '=', True)]):
            for device in vm['devices']:
                if device['dtype'] not in ('DISK', 'RAW'):
                    continue

                path = device['attributes'].get('path')
                if not path:
                    continue

                if path.startswith(f'/dev/zvol/{dataset_name}/') or path.startswith(f'/mnt/{dataset_name}/'):
                    result.append(vm)
                    break

        return result
