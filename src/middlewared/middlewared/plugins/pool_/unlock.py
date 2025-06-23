from middlewared.plugins.zfs_.utils import zvol_name_to_path
from middlewared.service import private, Service

from .utils import dataset_mountpoint


class PoolDatasetService(Service):

    class Config:
        namespace = 'pool.dataset'

    @private
    async def unlock_restarted_vms(self, dataset):
        result = []
        for vm in await self.middleware.call('vm.query', [('autostart', '=', True)]):
            for device in vm['devices']:
                if device['attributes']['dtype'] not in ('DISK', 'RAW'):
                    continue

                path = device['attributes'].get('path')
                if not path:
                    continue

                unlock = False
                if dataset['type'] == 'FILESYSTEM' and (mountpoint := dataset_mountpoint(dataset)):
                    unlock = path.startswith(mountpoint + '/') or path.startswith(
                        zvol_name_to_path(dataset['name']) + '/'
                    )
                elif dataset['type'] == 'VOLUME' and zvol_name_to_path(dataset['name']) == path:
                    unlock = True

                if unlock:
                    result.append(vm)
                    break

        return result

    @private
    async def restart_vms_after_unlock(self, dataset):
        for vm in await self.middleware.call('pool.dataset.unlock_restarted_vms', dataset):
            if (await self.middleware.call('vm.status', vm['id']))['state'] == 'RUNNING':
                stop_job = await self.middleware.call('vm.stop', vm['id'])
                await stop_job.wait()
                if stop_job.error:
                    self.logger.error('Failed to stop %r VM: %s', vm['name'], stop_job.error)
            try:
                await self.middleware.call('vm.start', vm['id'])
            except Exception:
                self.logger.error('Failed to start %r VM after %r unlock', vm['name'], dataset['name'], exc_info=True)
