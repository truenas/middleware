from middlewared.schema import accepts, Bool, Dict, Str
from middlewared.service import ConfigService, private
from middlewared.utils import Popen, run

import asyncio
import os
import shutil

SYSDATASET_PATH = '/var/db/system'


class SystemDatasetService(ConfigService):

    @accepts()
    async def config(self):
        return await self.middleware.call('datastore.config', 'system.systemdataset', {'prefix': 'sys_', 'extend': 'systemdataset.config_extend'})

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

        config['syslog'] = config.pop('syslog_usedataset')
        config['rrd'] = config.pop('rrd_usedataset')

        return config

    @accepts(Dict(
        'sysdataset_update',
        Str('pool'),
        Bool('syslog'),
        Bool('rrd'),
    ))
    async def do_update(self, data):
        config = await self.config()

        new = config.copy()
        new.update(data)

        new['syslog_usedataset'] = new['syslog']
        new['rrd_usedataset'] = new['rrd']
        await self.middleware.call('datastore.update', 'system.systemdataset', config['id'], new, {'prefix': 'sys_'})

        if 'pool' in data and data['pool'] != config['pool']:
            await self.migrate(config['pool'], data['pool'])

        if config['rrd'] != new['rrd']:
            # Stop collectd to flush data
            await self.middleware.call('service.stop', 'collectd')

        await self.setup()

        if config['syslog'] != new['syslog']:
            await self.middleware.call('service.restart', 'syslogd')

        if config['rrd'] != new['rrd']:
            await self.rrd_toggle()
            await self.middleware.call('service.restart', 'collectd')
        return config['id']

    @accepts(Bool('mount', default=True))
    @private
    async def setup(self, mount):
        if not await self.middleware.call('system.is_freenas'):
            if await self.middleware.call('notifier.failover_status') == 'BACKUP':
                try:
                    os.unlink(SYSDATASET_PATH)
                except OSError:
                    pass
                return

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

        datasets = [i[0] for i in self.__get_datasets(config['pool'], config['uuid'])]

        createdds = False
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

        if createdds:
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

            await self.__nfsv4link()

        return config

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
            await run('mount', '-t', 'zfs', dataset, mountpoint, check=False)

    async def __umount(self, pool, uuid):
        for dataset, name in reversed(self.__get_datasets(pool, uuid)):
            await run('umount', '-f', dataset, check=False)

    def __get_datasets(self, pool, uuid):
        return [(f'{pool}/.system', '')] + [
            (f'{pool}/.system/{i}', i) for i in [
                'cores', 'samba4', f'syslog-{uuid}',
                f'rrd-{uuid}', f'configs-{uuid}',
            ]
        ]

    @private
    def path(self):
        if not os.path.exists(SYSDATASET_PATH):
            return None

        if not os.path.ismount(SYSDATASET_PATH):
            return None

        return SYSDATASET_PATH

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

    async def __nfsv4link(self):
        syspath = self.path()
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

        rsyncs = (
            (SYSDATASET_PATH, '/tmp/system.new'),
        )

        if not os.path.exists('/tmp/system.new'):
            os.mkdir('/tmp/system.new')
        await self.__mount(_to, config['uuid'], path='/tmp/system.new')

        restart = ['syslogd', 'collectd']

        if await self.middleware.call('service.started', 'cifs'):
            restart.append('cifs')

        for i in restart:
            await self.middleware.call('service.stop', i)

        for src, dest in rsyncs:
            cp = await run('rsync', '-az', f'{src}/', dest)

        if _from and cp.returncode == 0:
            await self.__umount(_from, config['uuid'])
            await self.__umount(_to, config['uuid'])
            await self.__mount(_to, config['uuid'], SYSDATASET_PATH)
            proc = await Popen(f'zfs list -H -o name {_from}/.system|xargs zfs destroy -r')
            await proc.communicate()

        os.rmdir('/tmp/system.new')

        for i in restart:
            await self.middleware.call('service.start', i)

        await self.__nfsv4link()
