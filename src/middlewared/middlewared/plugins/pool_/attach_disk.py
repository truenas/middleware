import asyncio

from middlewared.schema import accepts, Bool, Dict, Int, returns, Str
from middlewared.service import job, Service, ValidationErrors


class PoolService(Service):

    @accepts(
        Int('oid'),
        Dict(
            'pool_attach',
            Str('target_vdev', required=True),
            Str('new_disk', required=True),
            Bool('allow_duplicate_serials', default=False),
        )
    )
    @returns()
    @job(lock=lambda args: f'pool_attach_{args[0]}')
    async def attach(self, job, oid, options):
        """
        For TrueNAS Core/Enterprise platform, if the `oid` pool is passphrase GELI encrypted, `passphrase`
        must be specified for this operation to succeed.

        `target_vdev` is the GUID of the vdev where the disk needs to be attached. In case of STRIPED vdev, this
        is the STRIPED disk GUID which will be converted to mirror. If `target_vdev` is mirror, it will be converted
        into a n-way mirror.
        """
        pool = await self.middleware.call('pool.get_instance', oid)
        verrors = ValidationErrors()
        if not pool['is_decrypted']:
            verrors.add('oid', 'Pool must be unlocked for this action.')
            verrors.check()
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
            if vdev['type'] not in ('DISK', 'MIRROR'):
                verrors.add('pool_attach.target_vdev', f'Attaching disk to {vdev["type"]} vdev is not allowed.')

        # Let's validate new disk now
        verrors.add_child(
            'pool_attach',
            await self.middleware.call('disk.check_disks_availability', [options['new_disk']],
                                       options['allow_duplicate_serials']),
        )
        verrors.check()

        guid = vdev['guid'] if vdev['type'] == 'DISK' else vdev['children'][0]['guid']
        disks = {options['new_disk']: {'create_swap': topology_type == 'data', 'vdev': []}}
        await self.middleware.call('pool.format_disks', job, disks)

        devname = disks[options['new_disk']]['vdev'][0]
        extend_job = await self.middleware.call('zfs.pool.extend', pool['name'], None, [
            {'target': guid, 'type': 'DISK', 'path': devname}
        ])
        await job.wrap(extend_job)

        asyncio.ensure_future(self.middleware.call('disk.swaps_configure'))
