# Copyright (c) 2019 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

import contextlib
import glob
import os
import re
import shutil
import subprocess

from middlewared.schema import accepts
from middlewared.service import CallError, SystemServiceService, job

ASIGRA_DSOPDIR = '/usr/local/www/asigra'


class AsigraService(SystemServiceService):

    class Config:
        service = "asigra"
        service_verb = "restart"
        datastore = "services.asigra"
        datastore_prefix = "asigra_"

    @accepts()
    @job(lock='migrate_asigra')
    def migrate_to_plugin(self, job):
        # We want to perform migration here for asigra service which intends to transfer the existing asigra content
        # over to an asigra plugin.
        # Following steps are taken to ensure a smooth migration:
        # 1) It is ensured that asigra migration should be performed for the system in question.
        # 2) We check for the existence of custom jail image which should be present in the latest iso
        # 3) We setup iocage as needed and import the jail
        # 4) Let's configure plugin jail's fstab to mount asigra datasets
        # 4a) We should set the ownership of the database correctly in the asigra dataset
        # 4b) Reword "Storage_Label.txt" in asigra dataset to correctly reflect the contents in asigra plugin
        # 4c) Destroy database contents in jail and zdata/root as jail plugin will not add them in fstab otherwise.
        # 4d) Finally add related mounts inside the jail
        # 5) Set asigra filesystem value as None which indicates that migration has been performed or not needed

        asigra_config = self.middleware.call_sync('asigra.config')
        if not asigra_config['filesystem']:
            self.middleware.logger.debug('No migration required for the current system.')
            return

        custom_jail_image = 'asigra_migration_image'
        custom_jail_image_path = glob.glob(f'/usr/local/share/{custom_jail_image}*zip')
        if not custom_jail_image_path:
            raise CallError('Custom asigra jail image does not exist.')
        else:
            custom_jail_image_path = custom_jail_image_path[0]
            # iocage expects zipped file to be "name_date.zip"
            custom_jail_image = custom_jail_image_path.split('/')[-1].rsplit('_', 1)[0]

        pool = None
        with contextlib.suppress(Exception):
            pool = self.middleware.call_sync('jail.get_activated_pool')

        if not pool:
            # In this case let's activate the pool being used by asigra dataset right now
            pool = asigra_config['filesystem'].split('/', 1)[0]
            if not self.middleware.call_sync('jail.activate', pool):
                raise CallError(f'Failed to activate {pool} for iocage pool.')

        # Ensure iocage datasets exist
        self.middleware.call_sync('jail.check_dataset_existence')
        job.set_progress(10, f'{pool} pool activated for iocage.')

        shutil.copy(custom_jail_image_path, os.path.join('/mnt', pool, 'iocage/images/'))

        import_job = self.middleware.call_sync('jail.import_image', custom_jail_image)
        import_job.wait_sync()
        if import_job.error:
            raise CallError(f'Importing custom jail image failed: {import_job.error}')

        if not self.middleware.call_sync('plugin.query', [['id', '=', custom_jail_image]]):
            raise CallError(f'Plugin jail {custom_jail_image} not found.')

        job.set_progress(25, 'Custom asigra plugin image imported.')

        iocroot = self.middleware.call_sync('jail.get_iocroot')
        plugin_root_path = os.path.join(iocroot, 'jails', custom_jail_image, 'root')
        plugin_postgres_home_path = os.path.join(plugin_root_path, 'usr/local/pgsql')
        system_asigra_path = os.path.join('/mnt', asigra_config['filesystem'])
        system_postgres_path = os.path.join(system_asigra_path, 'database')

        with open(os.path.join(plugin_root_path, 'etc/passwd'), 'r') as f:
            ids = re.findall(r'pgsql.*:(\d+):(\d+):', f.read())
            if not ids:
                raise CallError(f'postgres user could not be found in {custom_jail_image} jail.')
            else:
                uid, gid = ids[0]

        # TODO: Please make sure there are no drawbacks to this approach
        proc = subprocess.Popen(
            ['chown', '-R', f'{uid}:{gid}', system_postgres_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout, stderr = proc.communicate()

        if proc.returncode:
            raise CallError(f'Failed to set ownership of {system_postgres_path}: {stderr}')

        shutil.copy(
            os.path.join(plugin_root_path, 'zdata/root/Storage_Label.txt'),
            os.path.join(system_asigra_path, 'files/Storage_Label.txt')
        )

        shutil.rmtree(os.path.join(plugin_postgres_home_path, 'data'))
        shutil.rmtree(os.path.join(plugin_root_path, 'zdata/root'))

        job.set_progress(75, 'Asigra plugin setup complete for beginning of migration.')

        for source, destination in (
            (system_postgres_path, os.path.join(plugin_postgres_home_path, 'data')),
            (os.path.join(system_asigra_path, 'files'), os.path.join(plugin_root_path, 'zdata/root')),
            (os.path.join(system_asigra_path, 'upgrade'), os.path.join(plugin_root_path, 'zdata/Upgrade')),
            (os.path.join(system_asigra_path, 'tmp'), os.path.join(plugin_root_path, 'zdata/tmp')),
        ):
            self.middleware.call_sync(
                'jail.fstab',
                custom_jail_image, {
                    'action': 'ADD',
                    'source': source,
                    'destination': destination,
                }
            )

        self.middleware.call_sync('datastore.update', 'services.asigra', asigra_config['id'], {'filesystem': ''})
        self.middleware.logger.debug('Migration successfully performed.')
        job.set_progress(
            100, 'Asigra dataset mountpoints successfully added to asigra plugin fstab completing migration.'
        )


def _event_system(middleware, event_type, args):
    if args['id'] != 'ready':
        return

    middleware.call_sync('asigra.migrate_to_plugin')


async def setup(middleware):
    middleware.event_subscribe('system', _event_system)
