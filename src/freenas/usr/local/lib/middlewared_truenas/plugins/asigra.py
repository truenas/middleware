import contextlib
import os
import pwd
import re
import shutil
import subprocess
import tempfile
import textwrap


from middlewared.service import CallError, Service, private


class AsigraService(Service):

    class Config:
        service = "asigra"
        datastore_prefix = "asigra_"

    def __init__(self, middleware):
        super(AsigraService, self).__init__(middleware)

        self.pg_home = "/usr/local/pgsql"
        self.pg_user = "pgsql"
        self.pg_group = "pgsql"

        self.dssystem_path = "/usr/local/ds-system"
        self.dssystem_db_path = os.path.join(self.dssystem_path, "db")

        try:
            pw = pwd.getpwnam(self.pg_user)
            self.pg_user_uid = pw.pw_uid
            self.pg_group_gid = pw.pw_gid

        except Exception:
            self.pg_user_uid = 5432
            self.pg_group_gid = 5432

    @private
    def setup_filesystems(self):
        config = self.middleware.call_sync('datastore.config', 'services.asigra')

        if not config['filesystem']:
            return False

        if not self.middleware.call_sync('zfs.dataset.query', [('id', '=', config['filesystem'])]):
            return False

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
        if not os.path.exists(self.pg_home):
            os.mkdir(self.pg_home, mode=0o750)
            shutil.chown(self.pg_home, user=self.pg_user, group=self.pg_group)

        s = os.stat(self.pg_home)
        if (s.st_uid != self.pg_user_uid) or (s.st_gid != self.pg_group_gid):
            shutil.chown(self.pg_home, user=self.pg_user, group=self.pg_group)

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
            pg_conf_regex = re.compile('.*(#)\s{0,}?listen_addresses\s{0,}=\s{0,}([^\s]+)', re.M | re.S)
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
                pg_user=postgres
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
