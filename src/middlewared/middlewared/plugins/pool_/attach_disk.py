import asyncio

from middlewared.api import api_method
from middlewared.api.current import PoolAttachArgs, PoolAttachResult
from middlewared.service import job, Service, ValidationErrors


class PoolService(Service):

    @api_method(PoolAttachArgs, PoolAttachResult, roles=['POOL_WRITE'])
    @job(lock=lambda args: f'pool_attach_{args[0]}')
    async def attach(self, job, oid, options):
        """
        `target_vdev` is the GUID of the vdev where the disk needs to be attached. In case of STRIPED vdev, this
        is the STRIPED disk GUID which will be converted to mirror. If `target_vdev` is mirror, it will be converted
        into a n-way mirror.
        """
        pool = await self.middleware.call('pool.get_instance', oid)
        verrors = ValidationErrors()
        topology = pool['topology']
        topology_type = vdev = None
        for i in topology:
            for v in topology[i]:
                if v['guid'] == options['target_vdev']:
                    topology_type = i
                    vdev = v
                    break
            if topology_type:
                break
        else:
            verrors.add('pool_attach.target_vdev', 'Unable to locate VDEV')
            verrors.check()
        if topology_type in ('cache', 'spares'):
            verrors.add('pool_attach.target_vdev', f'Attaching disks to {topology_type} not allowed.')
        elif topology_type == 'data':
            # We would like to make sure here that we don't have inconsistent vdev types across data
            if vdev['type'] not in ('DISK', 'MIRROR', 'RAIDZ1', 'RAIDZ2', 'RAIDZ3'):
                verrors.add('pool_attach.target_vdev', f'Attaching disk to {vdev["type"]} vdev is not allowed.')

        # Let's validate new disk now
        verrors.add_child(
            'pool_attach',
            await self.middleware.call('disk.check_disks_availability', [options['new_disk']],
                                       options['allow_duplicate_serials']),
        )
        verrors.check()

        job.set_progress(3, 'Completed validation')

        if vdev['type'] in ['DISK', 'RAIDZ1', 'RAIDZ2', 'RAIDZ3']:
            guid = vdev['guid']
        else:
            guid = vdev['children'][0]['guid']

        if vdev['type'] == 'DISK':
            devices_for_size = [vdev.get('device')]
        else:
            devices_for_size = [child.get('device') for child in vdev['children']]

        sizes = []
        for device in devices_for_size:
            if device is not None:
                size = await self.middleware.call('disk.get_dev_size', device)
                if size is not None:
                    sizes.append(size)

        disks = {options['new_disk']: {'vdev': [], 'size': min(sizes) if sizes else None}}
        job.set_progress(5, 'Formatting disks')
        await self.middleware.call('pool.format_disks', job, disks, 5, 20)
        job.set_progress(22, 'Extending pool')
        devname = disks[options['new_disk']]['vdev'][0]
        extend_job = await self.middleware.call('zfs.pool.extend', pool['name'], None, [
            {'target': guid, 'type': 'DISK', 'path': devname}
        ])
        await extend_job.wait(raise_error=True)

        if vdev['type'] in ('RAIDZ1', 'RAIDZ2', 'RAIDZ3'):
            while True:
                expand = await self.middleware.call('zfs.pool.expand_state', pool['name'])

                if expand['state'] is None:
                    job.set_progress(25, 'Waiting for expansion to start')
                    await asyncio.sleep(1)
                    continue

                if expand['state'] == 'FINISHED':
                    job.set_progress(100, '')
                    break

                if expand['waiting_for_resilver']:
                    message = 'Paused for resilver or clear'
                else:
                    message = 'Expanding'

                job.set_progress(max(min(expand['percentage'], 95), 25), message)

                await asyncio.sleep(10 if expand['total_secs_left'] > 60 else 1)
