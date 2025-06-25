import contextlib
import ipaddress
from itertools import product
from typing import TYPE_CHECKING

from middlewared.common.attachment import FSAttachmentDelegate
from middlewared.common.ports import PortDelegate, ServicePortDelegate

from .utils import VirtGlobalStatus, INCUS_BRIDGE

if TYPE_CHECKING:
    from middlewared.main import Middleware


class VirtFSAttachmentDelegate(FSAttachmentDelegate):

    name = 'virt'
    title = 'Virtualization'
    service = 'incus'

    async def query(self, path, enabled, options=None):
        virt_config = await self.middleware.call('virt.global.config')

        instances = []
        pool = path.split('/')[2] if path.count('/') == 2 else None  # only set if path is pool mp
        dataset = path.removeprefix('/mnt/')
        incus_pool_change = dataset in virt_config['storage_pools'] or dataset == virt_config['pool']
        for i in await self.middleware.call('virt.instance.query'):
            append = False
            if pool and i['storage_pool'] == pool:
                instances.append({
                    'id': i['id'],
                    'name': i['name'],
                    'disk_devices': [],
                    'dataset': dataset,
                })
                continue

            disks = []
            for device in await self.middleware.call('virt.instance.device_list', i['id']):
                if device['dev_type'] != 'DISK':
                    continue

                if pool and device['storage_pool'] == pool:
                    append = True
                    disks.append(device['name'])
                    continue

                if device['source'] is None:
                    continue

                source_path = device['source'].removeprefix('/dev/zvol/').removeprefix('/mnt/')
                if await self.middleware.call('filesystem.is_child', source_path, dataset):
                    append = True
                    disks.append(device['name'])
                    continue

            if append:
                instances.append({
                    'id': i['id'],
                    'name': i['name'],
                    'disk_devices': disks,
                    'dataset': dataset,
                })

        return [{
            'id': dataset,
            'name': self.name,
            'instances': instances,
            'incus_pool_change': incus_pool_change,
        }] if incus_pool_change or instances else []

    async def delete(self, attachments):
        if not attachments:
            return

        # This is called in 3 cases:
        # 1) A dataset is being deleted which is being consumed by virt somehow
        # 2) A pool is being exported which is a storage pool in virt but not the main pool
        # 3) A pool is being exported which is the main pool of incus
        #
        # In (1), what we want to do is to remove the disks from the instances as incus does not like if a path
        # does not exist anymore and just flat out errors out, we intend to improve that but that will be a different
        # change/recovery mechanism.
        # In (2), we want to remove the disks from the instances which are using the pool and then unset the pool
        # For unsetting, we first unset the main pool as well because of a design decision taken when implementing this
        # to see if the storage pool being removed is being used anywhere and erroring out if that is the case.
        # After discussing with Andrew, we want to keep that as is. Which means we do something like
        # virt.global.update main_pool=None, storage_pools=[pool1, pool2] where exported pool is removed
        # Then we do virt.global.update main_pool=pool1, storage_pools=[pool1, pool2]
        # Finally for (3), there is nothing much to be done here in this regard and we can just unset the pool

        attachment = attachments[0]
        virt_config = await self.middleware.call('virt.global.config')
        storage_pools = [p for p in virt_config['storage_pools'] if p != attachment['id']]
        if attachment['incus_pool_change'] and attachment['id'] == virt_config['pool']:
            # We are exporting main virt pool and at this point we should just unset
            # the pool
            await (await self.middleware.call('virt.global.update', {
                'pool': None,
                'storage_pools': storage_pools,
            })).wait(raise_error=True)
            return

        disks_to_remove = [i for i in filter(lambda i: i.get('disk_devices'), attachment['instances'])]
        for instance_data in disks_to_remove:
            for to_remove_disk in instance_data['disk_devices']:
                await self.middleware.call('virt.instance.device_delete', instance_data['name'], to_remove_disk)

        if attachment['incus_pool_change']:
            # This means one of the storage pool is being exported
            new_config = {
                'pool': None,
                'storage_pools': storage_pools,
            }
            await (await self.middleware.call('virt.global.update', new_config)).wait(raise_error=True)
            await (await self.middleware.call(
                'virt.global.update', {'pool': virt_config['pool']}
            )).wait(raise_error=True)

    async def toggle(self, attachments, enabled):
        await getattr(self, 'start' if enabled else 'stop')(attachments)

    async def start(self, attachments):
        if not attachments:
            return

        attachment = attachments[0]
        if attachment['incus_pool_change']:
            try:
                await (await self.middleware.call('virt.global.setup')).wait(raise_error=True)
            except Exception:
                self.middleware.logger.error('Failed to start incus', exc_info=True)
                # No need to attempt to toggle instances, it won't happen either ways because none could be
                # queried to be started as incus wasn't even running but better safe than sorry
                return

        await self.start_instances(attachment['instances'])

    async def stop(self, attachments):
        if not attachments:
            return

        attachment = attachments[0]
        if attachment['incus_pool_change']:
            # Stopping incus service does not stop the instances
            # So let's make sure to stop them separately
            await self.stop_running_instances()
            try:
                await self.middleware.call('service.stop', self.service)
            except Exception:
                self.middleware.logger.error('Failed to stop incus', exc_info=True)
            finally:
                await self.middleware.call('virt.global.set_status', VirtGlobalStatus.LOCKED)
        else:
            await self.stop_instances(attachment['instances'])

    async def toggle_instances(self, attachments, enabled):
        for attachment in attachments:
            action = 'start' if enabled else 'stop'
            params = [{'force': True}] if action == 'stop' else []
            try:
                await (
                    await self.middleware.call(f'virt.instance.{action}', attachment['id'], *params)
                ).wait(raise_error=True)
            except Exception as e:
                self.middleware.logger.warning('Unable to %s %r: %s', action, attachment['id'], e)

    async def stop_instances(self, attachments):
        await self.toggle_instances(attachments, False)

    async def start_instances(self, attachments):
        await self.toggle_instances(attachments, True)

    async def disable(self, attachments):
        # This has been added explicitly because we do not want to call stop when we export a pool while still
        # wanting to maintain attachments as in incus case, this just breaks incus as it won't be able to boot
        # anymore. There are 2 cases here:
        # 1) Incus main pool being exported
        # 2) Incus storage pool being exported
        #
        # In both cases we remove any reference from virt as virt is practically left in a broken state
        # Please refer above in delete impl to see what happens in both cases
        await self.delete(attachments)

    async def stop_running_instances(self):
        # We need to stop all running instances before we can stop the service
        params = [
            [i['id'], {'force': True, 'timeout': 10}]
            for i in await self.middleware.call(
                'virt.instance.query', [('status', '=', 'RUNNING')],
                {'extra': {'skip_state': True}},
            )
        ]
        job = await self.middleware.call('core.bulk', 'virt.instance.stop', params, 'Stopping instances')
        await job.wait(raise_error=True)


class VirtPortDelegate(PortDelegate):

    name = 'virt instances'
    namespace = 'virt'
    title = 'Virtualization Device'

    async def get_ports(self):
        ports = []
        for instance_id, instance_ports in (await self.middleware.call('virt.instance.get_ports_mapping')).items():
            if instance_ports := list(product(['0.0.0.0', '::'], instance_ports)):
                ports.append({
                    'description': f'{instance_id!r} instance',
                    'ports': instance_ports,
                    'instance': instance_id,
                })
        return ports


class IncusServicePortDelegate(ServicePortDelegate):

    name = 'virt'
    namespace = 'virt.global'
    title = 'Virt Service'

    async def get_ports_internal(self):
        ports = []
        config = await self.middleware.call('virt.global.config')
        if config['state'] != VirtGlobalStatus.INITIALIZED.value:
            # No need to report ports if incus is not initialized
            return ports

        with contextlib.suppress(Exception):
            # Get incusbr0 network details from incus API
            bridge = config['bridge'] or INCUS_BRIDGE
            network_info = await self.middleware.call('virt.global.get_network', bridge)
            for family in ['ipv4_address', 'ipv6_address']:
                if network_info.get(family):
                    try:
                        # Extract IP address from CIDR notation
                        ip = ipaddress.ip_interface(network_info[family]).ip
                        ports.append((str(ip), 53))
                    except ValueError:
                        continue

        return ports


async def setup(middleware: 'Middleware'):
    middleware.create_task(
        middleware.call(
            'pool.dataset.register_attachment_delegate',
            VirtFSAttachmentDelegate(middleware),
        )
    )
    await middleware.call('port.register_attachment_delegate', VirtPortDelegate(middleware))
    await middleware.call('port.register_attachment_delegate', IncusServicePortDelegate(middleware))
