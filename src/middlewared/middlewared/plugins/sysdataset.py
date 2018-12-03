from middlewared.schema import accepts, Bool, Dict, Str
from middlewared.service import CallError, ConfigService, ValidationErrors, job, private
from middlewared.utils import Popen, run

import asyncio
import errno
import os
import psutil
import shutil
import subprocess
import tarfile
import time
import uuid

SYSDATASET_PATH = '/var/db/system'
SYSRRD_SENTINEL = '/data/sentinels/sysdataset-rrd-disable'


class SystemDatasetService(ConfigService):

    class Config:
        datastore = 'system.systemdataset'
        datastore_extend = 'systemdataset.config_extend'
        datastore_prefix = 'sys_'

    @private
    async def config_extend(self, config):

        # Add `is_decrypted` dynamic attribute
        if config['pool'] == 'freenas-boot':
            config['is_decrypted'] = True
        else:
            pool = await self.middleware.call('pool.query', [('name', '=', config['pool'])])
            if pool:
                config['is_decrypted'] = pool[0]['is_decrypted']
            else:
                config['is_decrypted'] = False

        if config['is_decrypted']:
            config['basename'] = f'{config["pool"]}/.system'
        else:
            config['basename'] = None

        # Make `uuid` point to the uuid of current node
        config['uuid_a'] = config['uuid']
        if not await self.middleware.call('system.is_freenas'):
            if await self.middleware.call('notifier.failover_node') == 'B':
                config['uuid'] = config['uuid_b']

        if not config['uuid']:
            config['uuid'] = uuid.uuid4().hex
            if (
                not await self.middleware.call('system.is_freenas') and
                await self.middleware.call('notifier.failover_node') == 'B'
            ):
                attr = 'uuid_b'
                config[attr] = config['uuid']
            else:
                attr = 'uuid'
            await self.middleware.call('datastore.update', 'system.systemdataset', config['id'], {f'sys_{attr}': config['uuid']})

        config['syslog'] = config.pop('syslog_usedataset')
        config['rrd'] = config.pop('rrd_usedataset')

        if not os.path.exists(SYSDATASET_PATH) or not os.path.ismount(SYSDATASET_PATH):
            config['path'] = None
        else:
            config['path'] = SYSDATASET_PATH

        return config

    @accepts(Dict(
        'sysdataset_update',
        Str('pool', null=True),
        Str('pool_exclude', null=True),
        Bool('syslog'),
        Bool('rrd'),
        update=True
    ))
    @job(lock='sysdataset_update')
    async def do_update(self, job, data):
        config = await self.config()

        new = config.copy()
        new.update(data)

        verrors = ValidationErrors()
        if new['pool'] and not await self.middleware.call(
            'zfs.pool.query', [('name', '=', new['pool'])]
        ):
            verrors.add('sysdataset_update.pool', f'Pool "{new["pool"]}" not found', errno.ENOENT)
        elif not new['pool']:
            for pool in await self.middleware.call('pool.query'):
                if data.get('pool_exclude') == pool['name']:
                    continue
                new['pool'] = pool['name']
                break
            else:
                new['pool'] = 'freenas-boot'
        verrors.check()

        new['syslog_usedataset'] = new['syslog']
        new['rrd_usedataset'] = new['rrd']
        await self.middleware.call('datastore.update', 'system.systemdataset', config['id'], new, {'prefix': 'sys_'})

        if config['pool'] != new['pool']:
            await self.migrate(config['pool'], new['pool'])

        if config['rrd'] != new['rrd']:
            # Stop collectd to flush data
            await self.middleware.call('service.stop', 'collectd')

        await self.setup()

        if config['syslog'] != new['syslog']:
            await self.middleware.call('service.restart', 'syslogd')

        if config['rrd'] != new['rrd']:
            await self.rrd_toggle()
            await self.middleware.call('service.restart', 'collectd')
        return await self.config()

    @accepts(Bool('mount', default=True), Str('exclude_pool', default=None, null=True))
    @private
    async def setup(self, mount, exclude_pool=None):
        config = await self.config()

        if not await self.middleware.call('system.is_freenas'):
            if await self.middleware.call('notifier.failover_status') == 'BACKUP' and \
                    ('basename' in config and config['basename'] and config['basename'] != 'freenas-boot/.system'):
                try:
                    os.unlink(SYSDATASET_PATH)
                except OSError:
                    pass
                return

        if config['pool'] and config['pool'] != 'freenas-boot':
            if not await self.middleware.call('pool.query', [('name', '=', config['pool'])]):
                job = await self.middleware.call('systemdataset.update', {
                    'pool': None, 'pool_exclude': exclude_pool,
                })
                await job.wait()
                if job.error:
                    raise CallError(job.error)
                config = await self.config()

        if not config['pool'] and not await self.middleware.call('system.is_freenas'):
            job = await self.middleware.call('systemdataset.update', {'pool': 'freenas-boot'})
            await job.wait()
            if job.error:
                raise CallError(job.error)
            config = await self.config()
        elif not config['pool']:
            pool = None
            for p in await self.middleware.call('pool.query', [], {'order_by': ['encrypt']}):
                if exclude_pool and p['name'] == exclude_pool:
                    continue
                if p['is_decrypted']:
                    pool = p
                    break
            if pool:
                job = await self.middleware.call('systemdataset.update', {'pool': pool['name']})
                await job.wait()
                if job.error:
                    raise CallError(job.error)
                config = await self.config()

        if not config['basename']:
            if os.path.exists(SYSDATASET_PATH):
                try:
                    os.rmdir(SYSDATASET_PATH)
                except Exception:
                    self.logger.debug('Failed to remove system dataset dir', exc_info=True)
            return config

        if not config['is_decrypted']:
            return

        if await self.__setup_datasets(config['pool'], config['uuid']):
            # There is no need to wait this to finish
            asyncio.ensure_future(self.middleware.call('service.restart', 'collectd'))

        if not os.path.isdir(SYSDATASET_PATH):
            if os.path.exists(SYSDATASET_PATH):
                os.unlink(SYSDATASET_PATH)
            os.mkdir(SYSDATASET_PATH)

        aclmode = await self.middleware.call('zfs.dataset.query', [('id', '=', config['basename'])])
        if aclmode and aclmode[0]['properties']['aclmode']['value'] == 'restricted':
            await self.middleware.call(
                'zfs.dataset.update',
                config['basename'],
                {'properties': {'aclmode': {'value': 'passthrough'}}},
            )

        if mount:

            await self.__mount(config['pool'], config['uuid'])

            corepath = f'{SYSDATASET_PATH}/cores'
            if os.path.exists(corepath):
                # FIXME: sysctl module not working
                await run('sysctl', f"kern.corefile='{corepath}/%N.core'")
                os.chmod(corepath, 0o775)

            await self.__nfsv4link(config)

        return config

    async def __setup_datasets(self, pool, uuid):
        """
        Make sure system datasets for `pool` exist and have the right mountpoint property
        """
        createdds = False
        datasets = [i[0] for i in self.__get_datasets(pool, uuid)]
        datasets_prop = {i['id']: i['properties'].get('mountpoint') for i in await self.middleware.call('zfs.dataset.query', [('id', 'in', datasets)])}
        for dataset in datasets:
            mountpoint = datasets_prop.get(dataset)
            if mountpoint and mountpoint['value'] != 'legacy':
                await self.middleware.call(
                    'zfs.dataset.update',
                    dataset,
                    {'properties': {'mountpoint': {'value': 'legacy'}}},
                )
            elif not mountpoint:
                await self.middleware.call('zfs.dataset.create', {
                    'name': dataset,
                    'properties': {'mountpoint': 'legacy'},
                })
                createdds = True
        return createdds

    async def __mount(self, pool, uuid, path=SYSDATASET_PATH):
        for dataset, name in self.__get_datasets(pool, uuid):
            if name:
                mountpoint = f'{path}/{name}'
            else:
                mountpoint = path
            if os.path.ismount(mountpoint):
                continue
            if not os.path.isdir(mountpoint):
                os.mkdir(mountpoint)
            await run('mount', '-t', 'zfs', dataset, mountpoint, check=True)

    async def __umount(self, pool, uuid):
        for dataset, name in reversed(self.__get_datasets(pool, uuid)):
            await run('umount', '-f', dataset, check=False)

    def __get_datasets(self, pool, uuid):
        return [(f'{pool}/.system', '')] + [
            (f'{pool}/.system/{i}', i) for i in [
                'cores', 'samba4', f'syslog-{uuid}',
                f'rrd-{uuid}', f'configs-{uuid}', 'webui',
            ]
        ]

    @private
    async def rrd_toggle(self):
        config = await self.config()

        # Path where collectd stores files
        rrd_path = '/var/db/collectd/rrd'
        # Path where rrd fies are stored in system dataset
        rrd_syspath = f'/var/db/system/rrd-{config["uuid"]}'

        if config['rrd']:
            # Move from tmpfs to system dataset
            if os.path.exists(rrd_path):
                if os.path.islink(rrd_path):
                    # rrd path is already a link
                    # so there is nothing we can do about it
                    return False
                cp = await run('rsync', '-a', f'{rrd_path}/', f'{rrd_syspath}/', check=False)
                return cp.returncode == 0
        else:
            # Move from system dataset to tmpfs
            if os.path.exists(rrd_path):
                if os.path.islink(rrd_path):
                    os.unlink(rrd_path)
            else:
                os.makedirs(rrd_path)
            cp = await run('rsync', '-a', f'{rrd_syspath}/', f'{rrd_path}/')
            return cp.returncode == 0
        return False

    async def __nfsv4link(self, config):
        syspath = config['path']
        if not syspath:
            return None

        restartfiles = ["/var/db/nfs-stablerestart", "/var/db/nfs-stablerestart.bak"]
        if not await self.middleware.call('system.is_freenas') and await self.middleware.call('notifier.failover_status') == 'BACKUP':
            return None

        for item in restartfiles:
            if os.path.exists(item):
                if os.path.isfile(item) and not os.path.islink(item):
                    # It's an honest to goodness file, this shouldn't ever happen...but
                    path = os.path.join(syspath, os.path.basename(item))
                    if not os.path.isfile(path):
                        # there's no file in the system dataset, so copy over what we have
                        # being careful to nuke anything that is there that happens to
                        # have the same name.
                        if os.path.exists(path):
                            shutil.rmtree(path)
                        shutil.copy(item, path)
                    # Nuke the original file and create a symlink to it
                    # We don't need to worry about creating the file on the system dataset
                    # because it's either been copied over, or was already there.
                    os.unlink(item)
                    os.symlink(path, item)
                elif os.path.isdir(item):
                    # Pathological case that should never happen
                    shutil.rmtree(item)
                    self.__createlink(syspath, item)
                else:
                    if not os.path.exists(os.readlink(item)):
                        # Dead symlink or some other nastiness.
                        shutil.rmtree(item)
                        self.__createlink(syspath, item)
            else:
                # We can get here if item is a dead symlink
                if os.path.islink(item):
                    os.unlink(item)
                self.__createlink(syspath, item)

    def __createlink(self, syspath, item):
        path = os.path.join(syspath, os.path.basename(item))
        if not os.path.isfile(path):
            if os.path.exists(path):
                # There's something here but it's not a file.
                shutil.rmtree(path)
            open(path, 'w').close()
        os.symlink(path, item)

    async def migrate(self, _from, _to):

        config = await self.config()

        await self.__setup_datasets(_to, config['uuid'])

        if _from:
            path = '/tmp/system.new'
            if not os.path.exists('/tmp/system.new'):
                os.mkdir('/tmp/system.new')
        else:
            path = SYSDATASET_PATH
        await self.__mount(_to, config['uuid'], path=path)

        restart = ['syslogd', 'collectd']

        if await self.middleware.call('service.started', 'cifs'):
            restart.append('cifs')

        try:
            for i in restart:
                await self.middleware.call('service.stop', i)

            if _from:
                cp = await run('rsync', '-az', f'{SYSDATASET_PATH}/', '/tmp/system.new', check=False)
                if cp.returncode == 0:
                    await self.__umount(_from, config['uuid'])
                    await self.__umount(_to, config['uuid'])
                    await self.__mount(_to, config['uuid'], SYSDATASET_PATH)
                    proc = await Popen(f'zfs list -H -o name {_from}/.system|xargs zfs destroy -r', shell=True)
                    await proc.communicate()

                os.rmdir('/tmp/system.new')
        finally:
            for i in restart:
                await self.middleware.call('service.start', i)

        await self.__nfsv4link(config)

    @private
    def remove(self, path, link_only=False):
        if os.path.exists(path):
            if os.path.islink(path):
                os.unlink(path)
            elif os.path.isdir(path) and not link_only:
                shutil.rmtree(path)
            elif not link_only:
                os.remove(path)

    @private
    def get_members(self, tar, prefix):
        for tarinfo in tar.getmembers():
            if tarinfo.name.startswith(prefix):
                tarinfo.name = tarinfo.name[len(prefix):]
                yield tarinfo

    @private
    def use_rrd_dataset(self):
        config = self.middleware.call_sync('systemdataset.config')
        is_freenas = self.middleware.call_sync('system.is_freenas')
        rrd_mount = ''
        if config['path']:
            rrd_mount = f'{config["path"]}/rrd-{config["uuid"]}'

        use_rrd_dataset = False
        if (
            rrd_mount and config['rrd'] and (
                is_freenas or (not is_freenas and self.middleware.call_sync('notifier.failover_status') != 'BACKUP')
            )
        ):
            use_rrd_dataset = True

        return use_rrd_dataset

    @private
    def update_collectd_dataset(self):
        config = self.middleware.call_sync('systemdataset.config')
        is_freenas = self.middleware.call_sync('system.is_freenas')
        rrd_mount = ''
        if config['path']:
            rrd_mount = f'{config["path"]}/rrd-{config["uuid"]}'

        use_rrd_dataset = self.use_rrd_dataset()

        # TODO: If not is_freenas: remove the rc.conf cache rc.conf.local will run again using the correct
        # collectd_enable. See #5019
        if is_freenas:
            try:
                os.remove('/var/tmp/freenas_config.md5')
            except FileNotFoundError:
                pass

        hostname = self.middleware.call_sync('system.info')['hostname']
        if not hostname:
            hostname = self.middleware.call_sync('network.configuration.config')['hostname']

        rrd_file = '/data/rrd_dir.tar.bz2'
        data_dir = '/var/db/collectd/rrd'
        disk_parts = psutil.disk_partitions()
        data_dir_is_ramdisk = len([d for d in disk_parts if d.mountpoint == data_dir and d.device == 'tmpfs']) > 0

        if use_rrd_dataset:
            if os.path.isdir(rrd_mount):
                if os.path.isdir(data_dir) and not os.path.islink(data_dir):
                    if data_dir_is_ramdisk:
                        # copy-umount-remove
                        subprocess.Popen(
                            ['cp', '-a', data_dir, f'{data_dir}.{time.strftime("%Y%m%d%H%M%S")}'],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE
                        ).communicate()

                        # Should we raise an exception if umount fails ?
                        subprocess.Popen(
                            ['umount', data_dir],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE
                        ).communicate()

                        self.remove(data_dir)
                    else:
                        shutil.move(data_dir, f'{data_dir}.{time.strftime("%Y%m%d%H%M%S")}')

                if os.path.realpath(data_dir) != rrd_mount:
                    self.remove(data_dir)
                    os.symlink(rrd_mount, data_dir)
            else:
                self.middleware.logger.error(f'{rrd_mount} does not exist or is not a directory')
                return None
        else:
            self.remove(data_dir, link_only=True)

            if not os.path.isdir(data_dir):
                os.makedirs(data_dir)

            # Create RAMdisk (if not already exists) for RRD files so they don't fill up root partition
            if not data_dir_is_ramdisk:
                subprocess.Popen(
                    ['mount', '-t', 'tmpfs', '-o', 'size=1g', 'tmpfs', data_dir],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE
                ).communicate()

        pwd = rrd_mount if use_rrd_dataset else data_dir
        if not os.path.exists(pwd):
            self.middleware.logger.error(f'{pwd} does not exist')
            return None

        if os.path.isfile(rrd_file):
            with tarfile.open(rrd_file) as tar:
                if 'collectd/rrd' in tar.getnames():
                    tar.extractall(pwd, self.get_members(tar, 'collectd/rrd/'))

            if use_rrd_dataset:
                self.remove(rrd_file)

        # Migrate from old version, where "${hostname}" was a real directory
        # and "localhost" was a symlink.
        # Skip the case where "${hostname}" is "localhost", so symlink was not
        # (and is not) needed.
        if (
            hostname != 'localhost' and os.path.isdir(os.path.join(pwd, hostname)) and not os.path.islink(
                os.path.join(pwd, hostname)
            )
        ):
            if os.path.exists(os.path.join(pwd, 'localhost')):
                if os.path.islink(os.path.join(pwd, 'localhost')):
                    self.remove(os.path.join(pwd, 'localhost'))
                else:
                    # This should not happen, but just in case
                    shutil.move(
                        os.path.join(pwd, 'localhost'),
                        os.path.join(pwd, f'localhost.bak.{time.strftime("%Y%m%d%H%M%S")}')
                    )
            shutil.move(os.path.join(pwd, hostname), os.path.join(pwd, 'localhost'))

        # Remove all directories except "localhost" and it's backups (that may be erroneously created by
        # running collectd before this script)
        to_remove_dirs = [
            os.path.join(pwd, d) for d in os.listdir(pwd)
            if not d.startswith('localhost') and os.path.isdir(os.path.join(pwd, d))
        ]
        for r_dir in to_remove_dirs:
            self.remove(r_dir)

        # Remove all symlinks (that are stale if hostname was changed).
        to_remove_symlinks = [
            os.path.join(pwd, l) for l in os.listdir(pwd)
            if os.path.islink(os.path.join(pwd, l))
        ]
        for r_symlink in to_remove_symlinks:
            self.remove(r_symlink)

        # Create "localhost" directory if it does not exist
        if not os.path.exists(os.path.join(pwd, 'localhost')):
            os.makedirs(os.path.join(pwd, 'localhost'))

        # Create "${hostname}" -> "localhost" symlink if necessary
        if hostname != 'localhost':
            os.symlink(os.path.join(pwd, 'localhost'), os.path.join(pwd, hostname))

        # Let's return a positive value to indicate that necessary collectd operations were performed successfully
        return True

    @private
    def rename_tarinfo(self, tarinfo):
        name = tarinfo.name.split('/', maxsplit=4)
        tarinfo.name = f'collectd/rrd/{"" if len(name) < 5 else name[-1]}'
        return tarinfo

    @private
    def sysrrd_disable(self):
        # skip if no sentinel is found
        if os.path.exists(SYSRRD_SENTINEL):
            systemdataset_config = self.middleware.call_sync('systemdataset.config')
            rrd_mount = f'{systemdataset_config["path"]}/rrd-{systemdataset_config["uuid"]}'
            if os.path.isdir(rrd_mount):
                # Let's create tar from system dataset rrd which collectd.conf understands
                with tarfile.open('/data/rrd_dir.tar.bz2', mode='w:bz2') as archive:
                    archive.add(rrd_mount, filter=self.rename_tarinfo)

            os.remove(SYSRRD_SENTINEL)
