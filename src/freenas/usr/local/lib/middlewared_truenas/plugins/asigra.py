# Copyright (c) 2019 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

import contextlib
import errno
import glob
import os
import pwd
import re
import shutil
import subprocess
import tempfile
import textwrap

from aiohttp import web
from middlewared.schema import Dict, Str, accepts
from middlewared.service import CallError, SystemServiceService, ValidationErrors, private

ASIGRA_DSOPDIR = '/usr/local/www/asigra'


class AsigraService(SystemServiceService):

    class Config:
        service = "asigra"
        service_verb = "restart"
        datastore = "services.asigra"
        datastore_prefix = "asigra_"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pg_user = "pgsql"
        self.pg_group = "pgsql"

        try:
            pw = pwd.getpwnam(self.pg_user)
            self.pg_user_uid = pw.pw_uid
            self.pg_group_gid = pw.pw_gid
            if not os.path.exists(pw.pw_dir):
                os.mkdir(pw.pw_dir)
        except Exception:
            self.pg_user_uid = 5432
            self.pg_group_gid = 5432

    @accepts(Dict(
        'asigra_update',
        Str('filesystem'),
        update=True,
    ))
    async def do_update(self, data):
        config = await self.config()
        new = config.copy()
        new.update(data)

        verrors = ValidationErrors()
        if not new.get('filesystem'):
            verrors.add('asigra_update.filesystem', 'Filesystem is required.')
        elif new['filesystem'] not in (await self.middleware.call('pool.filesystem_choices')):
            verrors.add('asigra_update.filesystem', 'Filesystem not found.', errno.ENOENT)
        if verrors:
            raise verrors

        await self._update_service(config, new)
        return await self.config()

    @private
    def setup_filesystems(self):
        config = self.middleware.call_sync('datastore.config', 'services.asigra')

        if not config['filesystem']:
            raise CallError('Configure a filesystem for Asigra DS-System.')

        if not self.middleware.call_sync('zfs.dataset.query', [('id', '=', config['filesystem'])]):
            raise CallError(f'Filesystem {config["filesystem"]!r} not found.')

        filesystems = ('files', 'database', 'upgrade')
        for fs in filesystems:
            fs = f'{config["filesystem"]}/{fs}'
            if self.middleware.call_sync('zfs.dataset.query', [('id', '=', fs)]):
                continue
            proc = subprocess.Popen(
                ['zfs', 'create', fs], stdout=subprocess.PIPE, stderr=subprocess.STDOUT
            )
            stdout = proc.communicate()[0]
            if proc.returncode != 0:
                self.logger.error('Failed to create %s: %s', fs, stdout.decode())
                return False

    @private
    def setup_postgresql(self):
        asigra_config = None
        for row in self.middleware.call_sync('datastore.query', 'services.asigra'):
            asigra_config = row
        if not asigra_config:
            return False

        asigra_postgresql_path = f'/mnt/{asigra_config["filesystem"]}/database'
        if not asigra_config["filesystem"] or not os.path.exists(asigra_postgresql_path):
            return False

        asigra_postgresql_conf = os.path.join(asigra_postgresql_path, "postgresql.conf")
        asigra_pg_hba_conf = os.path.join(asigra_postgresql_path, "pg_hba.conf")

        # pgsql user home must exist before we can initialize postgresql data
        if not os.path.exists(asigra_postgresql_path):
            os.mkdir(asigra_postgresql_path, mode=0o750)
            shutil.chown(asigra_postgresql_path, user=self.pg_user, group=self.pg_group)

        s = os.stat(asigra_postgresql_path)
        if (s.st_uid != self.pg_user_uid) or (s.st_gid != self.pg_group_gid):
            shutil.chown(asigra_postgresql_path, user=self.pg_user, group=self.pg_group)

        if not os.path.exists(asigra_postgresql_path):
            os.mkdir(asigra_postgresql_path, mode=0o750)
            shutil.chown(asigra_postgresql_path, user=self.pg_user, group=self.pg_group)

        s = os.stat(asigra_postgresql_path)
        if (s.st_uid != self.pg_user_uid) or (s.st_gid != self.pg_group_gid):
            shutil.chown(asigra_postgresql_path, user=self.pg_user, group=self.pg_group)

        if not os.path.exists(asigra_pg_hba_conf):
            proc = subprocess.Popen(
                ['/usr/local/etc/rc.d/postgresql', 'oneinitdb'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                close_fds=True
            )
            output = (proc.communicate())[0].decode()
            if proc.returncode != 0:
                self.logger.error(output)
                self.logger.error('Failed to initialize postgresql:\n{}'.format(output))
                return False

            self.logger.debug(output)

            subprocess.Popen(
                ['/usr/sbin/chown', '-R', '{}:{}'.format(
                    self.pg_user, self.pg_group), asigra_postgresql_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                close_fds=True
            ).wait()

            if not os.path.exists(asigra_postgresql_conf):
                self.logger.error("{} doesn't exist!".format(asigra_postgresql_conf))
                return

            # listen_address = '*'
            pg_conf_regex = re.compile(r'.*(#)\s{0,}?listen_addresses\s{0,}=\s{0,}([^\s]+)', re.M | re.S)
            pg_conf_buf = []
            rewrite = False

            with open(asigra_postgresql_conf, "r") as f:
                for line in f:
                    if pg_conf_regex.search(line):
                        def pg_re_replace(m):
                            if m and len(m.groups()) > 1:
                                return m.group(0)[m.end(1):m.start(2)] + "'*'" + m.group(0)[m.end(2):]

                        line = pg_conf_regex.sub(pg_re_replace, line)
                        rewrite = True
                    pg_conf_buf.append(line)

            if rewrite and pg_conf_buf:
                with open(asigra_postgresql_conf, "w") as f:
                    f.write("".join(pg_conf_buf))

            if not os.path.exists(asigra_pg_hba_conf):
                self.logger.error("{} doesn't exist!".format(asigra_pg_hba_conf))
                return False

            # allow local access
            with open(asigra_pg_hba_conf, "a") as f:
                f.write("host\tall\tall\t127.0.0.0/24\ttrust")

        return True

    @private
    def setup_asigra(self):
        asigra_config = None
        for row in self.middleware.call_sync('datastore.query', 'services.asigra'):
            asigra_config = row
        if not asigra_config:
            return False

        asigra_path = f'/mnt/{asigra_config["filesystem"]}/files'
        if not asigra_config["filesystem"] or not os.path.exists(asigra_path):
            return False

        f = None
        try:
            f = tempfile.NamedTemporaryFile(mode='w+', delete=False)
            # Copied from dssystem pkg install manifest
            f.write(textwrap.dedent(
                '''#!/bin/sh
                pg_client_default=/usr/local/bin/psql
                pg_user=pgsql
                pg_host=/tmp/
                dest_dir=/usr/local/ds-system
                echo command: ${pg_client_default} -U ${pg_user} $opt -h ${pg_host} -l -d template1
                if [ -z "`${pg_client_default} -U ${pg_user} $opt -h ${pg_host} -l -d template1  | grep dssystem`"         ];then
                        echo there is no dssystem database found in the postgres database. Creating ...
                        ${pg_client_default} -U ${pg_user} $opt -h ${pg_host} -c "create database dssystem" -d template1
                        ${pg_client_default} -U ${pg_user} $opt -h ${pg_host} -f ${dest_dir}/db/postgresdssystem.sql -d dssystem
                        ${pg_client_default} -U ${pg_user} $opt -h ${pg_host} -f ${dest_dir}/db/dssystem_locale_postgres.sql -d dssystem
                else
                        MAX=`for i in /usr/local/ds-system/db/dssp*.sql;do
                                echo ${i##*/}
                             done | sed -e "s/dssp//g" -e "s/.sql//g" | awk 'BEGIN{max=0}{if ($1 > max)max=$1}END{print max}'`
                        db_number=`${pg_client_default} -U ${pg_user} $opt -h ${pg_host} -c "select db_number from ds_data" -d dssystem | sed -n "3p" | awk '{print $1}'`
                        if [ -n "`echo $db_number | grep -E '^-?[0-9][0-9]*$'`" ];then
                                if [ "`echo $db_number | grep -E -o '^-'`" == "-" ];then
                                        db_number=`echo $db_number | sed "s/^-//g"`
                                fi
                        fi

                        db_number=`expr $db_number + 1`
                        while [ $MAX -ge $db_number ];do
                                ${pg_client_default} -U ${pg_user} $opt -h ${pg_host} -f ${dest_dir}/db/dssp${db_number}.sql -d dssystem
                                echo apply the patch dssp${db_number}.sql
                                db_number=`expr $db_number + 1`
                        done
                fi
                '''
            ))
            f.close()
            os.chmod(f.name, 0o544)

            proc = subprocess.Popen([f.name], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stderr = proc.communicate()[1]
        finally:
            if f:
                with contextlib.suppress(OSError):
                    os.unlink(f.name)

        if proc.returncode != 0:
            raise CallError(f'Failed to setup database: {stderr.decode()}')

        return True

    @accepts()
    def migrate_to_plugin(self):
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

        shutil.copy(custom_jail_image_path, os.path.join('/mnt', pool, 'iocage/images/'))

        import_job = self.middleware.call_sync('jail.import_image', custom_jail_image)
        import_job.wait_sync()
        if import_job.error:
            raise CallError(f'Importing custom jail image failed: {import_job.error}')

        if not self.middleware.call_sync('plugin.query', [['id', '=', custom_jail_image]]):
            raise CallError(f'Plugin jail {custom_jail_image} not found.')

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


async def dsoperator_jnlp(request):
    """
    HTTP dynamic request to serve DSOP.jnlp replacing the URL to grab
    the .jar files.
    """
    dsop_jnlp = f'{ASIGRA_DSOPDIR}/DSOP.jnlp'
    if not os.path.exists(dsop_jnlp):
        return web.Response(status=404)

    with open(dsop_jnlp, 'rb') as f:
        data = f.read()
    data = data.replace(
        b'http://192.168.50.142:8080/CDPA/dsoper/',
        f'{request.scheme}://{request.host}/_plugins/asigra/static/'.encode()
    )
    data = data.replace(
        b'DSOP.jnlp',
        f'../DSOP.jnlp'.encode()
    )
    return web.Response(body=data, headers={
        'Content-Disposition': 'attachment; filename="DSOP.jnlp"',
        'Content-Length': str(len(data)),
        'Content-Type': 'application/x-java-jnlp-file',
    })


def _event_system(middleware, event_type, args):
    if args['id'] != 'ready':
        return

    middleware.call_sync('asigra.migrate_to_plugin')


async def setup(middleware):
    middleware.plugin_route_add('asigra', 'DSOP.jnlp', dsoperator_jnlp)
    middleware.event_subscribe('system', _event_system)
