from middlewared.plugins.zfs_.utils import zvol_name_to_path
from middlewared.schema import Dict, returns, Str
from middlewared.service import accepts, private, Service

from .utils import dataset_mountpoint


class PoolDatasetService(Service):

    class Config:
        namespace = 'pool.dataset'

    @accepts(Str('dataset'))
    @returns(Dict('services_to_restart', additional_attrs=True))
    async def unlock_services_restart_choices(self, dataset):
        """
        Get a mapping of services identifiers and labels that can be restart on dataset unlock.
        """
        dataset_instance = await self.middleware.call('pool.dataset.get_instance', dataset)
        services = {
            'cifs': 'SMB',
            'ftp': 'FTP',
            'iscsitarget': 'iSCSI',
            'nfs': 'NFS',
            'webdav': 'WebDAV',
        }

        result = {}
        for k, v in services.items():
            if await self.middleware.call('service.started_or_enabled', k):
                result[k] = v

        check_services = {
            'kubernetes': 'Applications',
            's3': 'S3',
            **services
        }

        result.update({
            k: check_services[k] for k in map(
                lambda a: a['service'], await self.middleware.call('pool.dataset.attachments', dataset)
            ) if k in check_services
        })

        if await self.middleware.call('pool.dataset.unlock_restarted_vms', dataset_instance):
            result['vms'] = 'Virtual Machines'

        return result

    @private
    async def unlock_restarted_vms(self, dataset):
        result = []
        for vm in await self.middleware.call('vm.query', [('autostart', '=', True)]):
            for device in vm['devices']:
                if device['dtype'] not in ('DISK', 'RAW'):
                    continue

                path = device['attributes'].get('path')
                if not path:
                    continue

                if (
                    (
                        dataset['type'] == 'FILESYSTEM' and
                        (mountpoint := dataset_mountpoint(dataset)) and
                        path.startswith(mountpoint + '/')
                    ) or
                    (dataset['type'] == 'VOLUME' and path.startswith(zvol_name_to_path(dataset['name']) + '/'))
                ):
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

    @private
    async def restart_services_after_unlock(self, dataset_name, services_to_restart):
        try:
            to_restart = [[i] for i in set(services_to_restart)]
            if not to_restart:
                return

            restart_job = await self.middleware.call('core.bulk', 'service.restart', to_restart)
            statuses = await restart_job.wait()
            for idx, srv_status in enumerate(statuses):
                if srv_status['error']:
                    self.logger.error(
                        'Failed to restart %r service after %r unlock: %s',
                        to_restart[idx], dataset_name, srv_status['error']
                    )
        except Exception:
            self.logger.error(
                'Failed to restart %r services after %r unlock', ', '.join(services_to_restart), id, exc_info=True,
            )
