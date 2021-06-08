import logging
import os
import shutil
import subprocess

from middlewared.job import Pipes
from middlewared.service import CallError, item_method, job, Service
from middlewared.schema import accepts, Dict, Int, returns, Str
from middlewared.utils import osc, run
from middlewared.utils.shell import join_commandline


logger = logging.getLogger(__name__)

# platform specific imports
if osc.IS_FREEBSD:
    import sysctl


class PoolService(Service):

    @item_method
    @accepts(
        Int('id'),
        Dict(
            'options',
            Dict(
                'geli',
                Str('passphrase', private=True, default=''),
            ),
        )
    )
    @returns()
    @job(lock='pool_expand')
    async def expand(self, job, id, options):
        """
        Expand pool to fit all available disk space.
        """
        pool = await self.middleware.call('pool.get_instance', id)
        if osc.IS_LINUX:
            if options.get('passphrase'):
                raise CallError('Passphrase should not be supplied for this platform.')
            # FIXME: We have issues in ZoL where when pool is created with partition uuids, we are unable
            #  to expand pool where all pool related options error out saying I/O error
            #  https://github.com/zfsonlinux/zfs/issues/9830
            raise CallError('Expand is not supported on this platform yet because of underlying ZFS issues.')
        else:
            if pool['encrypt']:
                if not pool['is_decrypted']:
                    raise CallError('You can only expand decrypted pool')

                for error in (
                    await self.middleware.call('pool.pool_lock_pre_check', pool, options['geli']['passphrase'])
                ).errors:
                    raise CallError(error.errmsg)

        all_partitions = {p['name']: p for p in await self.middleware.call('disk.list_all_partitions')}

        try:
            if osc.IS_FREEBSD:
                sysctl.filter('kern.geom.debugflags')[0].value = 16
            geli_resize = []
            vdevs = []
            try:
                for vdev in sum(pool['topology'].values(), []):
                    if vdev['status'] != 'ONLINE':
                        logger.debug('Not expanding vdev(%r) that is %r', vdev['guid'], vdev['status'])
                        continue

                    c_vdevs = []
                    disks = vdev['children'] if vdev['type'] != 'DISK' else [vdev]
                    skip_vdev = None
                    for child in disks:
                        if child['status'] != 'ONLINE':
                            skip_vdev = f'Device "{child["device"]}" status is not ONLINE ' \
                                        f'(Reported status is {child["status"]})'
                            break

                        part_data = all_partitions.get(child['device'])
                        if not part_data:
                            skip_vdev = f'Unable to find partition data for {child["device"]}'
                        elif not part_data['partition_number']:
                            skip_vdev = f'Could not parse partition number from {child["device"]}'
                        elif part_data['disk'] != child['disk']:
                            skip_vdev = f'Retrieved partition data for device {child["device"]} ' \
                                        f'({part_data["disk"]}) does not match with disk ' \
                                        f'reported by ZFS ({child["disk"]})'
                        if skip_vdev:
                            break
                        else:
                            c_vdevs.append((child['guid'], part_data))

                    if skip_vdev:
                        logger.debug('Not expanding vdev(%r): %r', vdev['guid'], skip_vdev)
                        continue

                    for guid, part_data in c_vdevs:
                        await self._resize_disk(part_data, pool['encrypt'], geli_resize)
                        vdevs.append(guid)
            finally:
                if osc.IS_FREEBSD and geli_resize:
                    await self.__geli_resize(pool, geli_resize, options)
        finally:
            if osc.IS_FREEBSD:
                sysctl.filter('kern.geom.debugflags')[0].value = 0

        # spare/cache devices cannot be expanded
        # We resize them anyways, for cache devices, whenever we are going to import the pool
        # next, it will register the new capacity. For spares, whenever that spare is going to
        # be used, it will register the new capacity as desired.
        for topology_type in filter(
            lambda t: t not in ('spare', 'cache') and pool['topology'][t], pool['topology']
        ):
            for vdev in pool['topology'][topology_type]:
                for c_vd in filter(
                    lambda v: v['guid'] in vdevs, vdev['children'] if vdev['type'] != 'DISK' else [vdev]
                ):
                    await self.middleware.call('zfs.pool.online', pool['name'], c_vd['guid'], True)

    async def _resize_disk(self, part_data, encrypted_pool, geli_resize):
        partition_number = part_data['partition_number']
        if osc.IS_LINUX:
            await run(
                'sgdisk', '-d', str(partition_number), '-n', f'{partition_number}:0:0',
                '-c', '2:', '-u', f'{partition_number}:{part_data["partition_uuid"]}',
                '-t', f'{partition_number}:BF01', part_data['path']
            )
            await run('partprobe', os.path.join('/dev', part_data['disk']))
        else:
            if not part_data['disk'].startswith('nvd'):
                await run('camcontrol', 'reprobe', part_data['disk'])
            await run('gpart', 'recover', part_data['disk'])
            await run('gpart', 'resize', '-a', '4k', '-i', str(partition_number), part_data['disk'])

        if osc.IS_FREEBSD and encrypted_pool:
            geli_resize_cmd = (
                'geli', 'resize', '-a', '4k', '-s', str(part_data['size']), part_data['name']
            )
            rollback_cmd = (
                'gpart', 'resize', '-a', '4k', '-i', str(partition_number),
                '-s', str(part_data['size']), part_data['disk']
            )

            logger.warning('It will be obligatory to notify GELI that the provider has been resized: %r',
                           join_commandline(geli_resize_cmd))
            logger.warning('Or to resize provider back: %r',
                           join_commandline(rollback_cmd))
            geli_resize.append((geli_resize_cmd, rollback_cmd))

    async def __geli_resize(self, pool, geli_resize, options):
        failed_rollback = []

        lock_job = await self.middleware.call('pool.lock', pool['id'], options['geli']['passphrase'])
        await lock_job.wait()
        if lock_job.error:
            logger.warning('Error locking pool: %s', lock_job.error)

            for geli_resize_cmd, rollback_cmd in geli_resize:
                if not await self.__run_rollback_cmd(rollback_cmd):
                    failed_rollback.append(rollback_cmd)

            if failed_rollback:
                raise CallError(
                    'Locking your encrypted pool failed and rolling back changes failed too. '
                    f'You\'ll need to run the following commands manually:\n%s' % '\n'.join(
                        map(join_commandline, failed_rollback)
                    )
                )
        else:
            for geli_resize_cmd, rollback_cmd in geli_resize:
                try:
                    await run(*geli_resize_cmd, encoding='utf-8', errors='ignore')
                except subprocess.CalledProcessError as geli_resize_error:
                    if geli_resize_error.stderr.strip() == 'geli: Size hasn\'t changed.':
                        logger.info(
                            '%s: %s', join_commandline(geli_resize_cmd), geli_resize_error.stderr.strip()
                        )
                    else:
                        logger.error(
                            '%r failed: %s. Resizing partition back', join_commandline(geli_resize_cmd),
                            geli_resize_error.stderr.strip()
                        )
                        if not await self.__run_rollback_cmd(rollback_cmd):
                            failed_rollback.append(rollback_cmd)

            if failed_rollback:
                raise CallError(
                    'Resizing partitions of your encrypted pool failed and rolling back '
                    'changes failed too. You\'ll need to run the following commands manually:\n%s' %
                    '\n'.join(map(join_commandline, failed_rollback))
                )

            if options['geli']['passphrase']:
                unlock_job = await self.middleware.call(
                    'pool.unlock', pool['id'], {'passphrase': options['geli']['passphrase']}
                )
            else:
                unlock_job = await self.middleware.call(
                    'pool.unlock', pool['id'], {'recoverykey': True},
                    pipes=Pipes(input=self.middleware.pipe())
                )

                def copy():
                    with open(pool['encryptkey_path'], 'rb') as f:
                        shutil.copyfileobj(f, unlock_job.pipes.input.w)

                try:
                    await self.middleware.run_in_thread(copy)
                finally:
                    await self.middleware.run_in_thread(unlock_job.pipes.input.w.close)

            await unlock_job.wait()
            if unlock_job.error:
                raise CallError(unlock_job.error)

    @staticmethod
    async def __run_rollback_cmd(rollback_cmd):
        try:
            await run(*rollback_cmd, encoding='utf-8', errors='ignore')
        except subprocess.CalledProcessError as rollback_error:
            logger.critical(
                '%r failed: %s. To restore your pool functionality you will have to run this command manually.',
                join_commandline(rollback_cmd),
                rollback_error.stderr.strip()
            )
            return False
        else:
            return True
