from middlewared.schema import accepts, Bool
from middlewared.service import ConfigService, private

import os

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

        # Make `uuid` point to the uuid of current node
        config['uuid_a'] = config['uuid']
        if not await self.middleware.call('system.is_freenas'):
            if await self.middleware.call('notifier.failover_node') == 'B':
                config['uuid'] = config['uuid_b']

        return config

    @accepts(Bool('mount'))
    @private
    async def setup(self, mount=True):
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

        datasets = [config['basename']]
        for sub in (
            'cores', 'samba4', f'syslog-{config["uuid"]}',
            f'rrd-{config["uuid"]}', f'configs-{config["uuid"]}',
        ):
            datasets.append(f'{config["basename"]}/{sub}')

        createdds = False
        for dataset in datasets:
            # TODO: use zfs plugin
            proc = await Popen([
                'zfs', 'get', '-H', '-o', 'value', 'mountpoint', dataset,
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                if stdout.decode().strip() != 'legacy':
                    await run('zfs', 'set', 'mountpoint=legacy', dataset, check=False)
                continue

            await self.middleware.call('zfs.dataset.create', {
                'name': dataset,
                'properties': {'mountpoint': 'legacy'},
            })
            createdds = True

        if createdds:
            self.middleware.call('service.restart', 'collectd')

        if not os.path.isdir(SYSDATASET_PATH):
            if os.path.exists(SYSDATASET_PATH):
                os.unlink(SYSDATASET_PATH)
            os.mkdir(SYSDATASET_PATH)

        # TODO: use zfs plugin
        proc = await Popen([
            'zfs', 'get', '-H', '-o', 'value', 'aclmode', dataset,
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = await proc.communicate()
        aclmode = stdout.decode().strip()
        if aclmode and aclmode.lower() == 'restricted':
            await run('zfs', 'set', 'aclmode=passthrough', basename, check=False)

        if mount:
            #self.system_dataset_mount(systemdataset.sys_pool, SYSDATASET_PATH)

            corepath = f'{SYSDATASET_PATH}/cores'
            if os.path.exists(corepath):
                # FIXME: sysctl module not working
                run('sysctl', f"kern.corefile='{corepath}/%N.core'")
                os.chmod(corepath, 0o775)

            #self.nfsv4link()

        return systemdataset
