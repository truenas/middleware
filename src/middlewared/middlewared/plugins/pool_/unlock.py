from middlewared.schema import Dict, returns, Str
from middlewared.service import accepts, private, Service


class PoolDatasetService(Service):

    class Config:
        namespace = 'pool.dataset'
        event_send = False

    @accepts(Str('dataset'))
    @returns(Dict('services_to_restart', additional_attrs=True))
    async def unlock_services_restart_choices(self, dataset):
        """
        Get a mapping of services identifiers and labels that can be restart on dataset unlock.
        """
        await self.middleware.call('pool.dataset.get_instance', dataset)
        services = {
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

    @private
    async def restart_vms_after_unlock(self, dataset_name):
        for vm in await self.unlock_restarted_vms(dataset_name):
            if await self.middleware.call('vm.status', vm['id'])['state'] == 'RUNNING':
                stop_job = await self.middleware.call('vm.stop', vm['id'])
                await stop_job.wait()
                if stop_job.error:
                    self.logger.error('Failed to stop %r VM: %s', vm['name'], stop_job.error)
            try:
                self.middleware.call_sync('vm.start', vm['id'])
            except Exception:
                self.logger.error('Failed to start %r VM after %r unlock', vm['name'], dataset_name, exc_info=True)

    @private
    async def restart_services_after_unlock(self, dataset_name, services_to_restart):
        try:
            to_restart = [[i] for i in set(services_to_restart) - {'vms'}]
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
            if 'vms' in services_to_restart:
                await self.middleware.call('pool.dataset.restart_vms_after_unlock', dataset_name)
        except Exception:
            self.logger.error(
                'Failed to restart %r services after %r unlock', ', '.join(services_to_restart), id, exc_info=True,
            )
