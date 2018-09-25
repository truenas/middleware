import glob
import os
import psycopg2 as pg
import pwd
import re
import shutil
import subprocess

from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from middlewared.service import Service, private
from subprocess import Popen


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

    # Use etc plugin for this?
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
            proc = Popen(
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

            Popen(
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

    # XXX
    # We should probably write a postgresql middleware plugin
    # We should also pass around a persistent DB handle
    # XXX
    def asigra_database_exists(self):
        exists = False
        con = None

        try:
            con = pg.connect("dbname='template1' user='{}'".format(self.pg_user))

        except Exception as e:
            self.logger.error("Can't connect to template1: {}".format(e))
            return exists

        cur = con.cursor()
        try:
            cur.execute("SELECT COUNT(*) from pg_database where datname = 'dssystem'")

        except Exception as e:
            self.logger.error("Can't query dssystem!: {}".format(e))
            return exists

        exists = False
        try:
            exists = (cur.fetchone()[0] != 0)
        except Exception:
            exists = False

        cur.close()
        con.close()

        return exists

    def asigra_database_create(self):
        con = None

        try:
            con = pg.connect("dbname='template1' user='{}'".format(self.pg_user))

        except Exception as e:
            self.logger.error("Can't connect to template1: {}".format(e))
            return False

        con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = con.cursor()

        try:
            self.logger.debug("there is no dssystem database found in the postgres database. Creating ...")
            cur.execute("CREATE DATABASE dssystem")

        except Exception as e:
            self.logger.error("Can't create dssystem database: {}".format(e))
            return False

        cur.close()
        con.close()

        return True

    def asigra_database_init(self):
        con = None

        try:
            con = pg.connect("dbname='dssystem' user='{}'".format(self.pg_user))

        except Exception as e:
            self.logger.error("Can't connect to dssystem: {}".format(e))
            return False

        con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = con.cursor()

        with open(os.path.join(self.dssystem_db_path, "postgresdssystem.sql"), "r") as f:
            try:
                cur.execute(f.read())

            except Exception as e:
                self.logger.error("Can't init dssystem database: {}".format(e))
                return False

        with open(os.path.join(self.dssystem_db_path, "dssystem_locale_postgres.sql"), "r") as f:
            try:
                cur.execute(f.read())

            except Exception as e:
                self.logger.error("Can't init dssystem database: {}".format(e))
                return False

        cur.close()
        con.close()

        return True

    def get_db_number(self):
        db_number = 0
        con = None

        try:
            con = pg.connect("dbname='dssystem' user='{}'".format(self.pg_user))

        except Exception as e:
            self.logger.error("Can't connect to dssystem: {}".format(e))
            return db_number

        cur = con.cursor()
        try:
            cur.execute("SELECT db_number FROM ds_data")

        except Exception as e:
            self.logger.error("Can't get db_number: {}".format(e))
            return db_number

        try:
            db_number = cur.fetchone()[0]

        except Exception as e:
            self.logger.error("Can't get db_number results: {}".format(e))
            return db_number

        cur.close()
        con.close()

        return db_number

    def asigra_database_update(self):
        con = None

        try:
            con = pg.connect("dbname='dssystem' user='{}'".format(self.pg_user))

        except Exception as e:
            self.logger.error("Can't connect to dssystem: {}".format(e))
            return False

        con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = con.cursor()

        files = glob.glob("{}/dssp*.sql".format(self.dssystem_db_path))

        max = 0
        for f in files:
            m = re.match('.*/dssp([0-9]+).sql', f)
            if not m or len(m.groups()) != 1:
                continue
            if int(m.group(1)) > max:
                max = int(m.group(1))

        db_number = self.get_db_number()
        if db_number < 0:
            db_number *= -1

        db_number += 1
        while max >= db_number:
            sql_patch = os.path.join(self.dssystem_db_path, "dssp{}.sql".format(db_number))

            self.logger.debug("apply the patch dssp{}.sql".format(db_number))
            with open(sql_patch, "r") as f:
                try:
                    cur.execute(f.read())

                except Exception as e:
                    self.logger.error("Can't init dssystem database: {}".format(e))
                    return False

            db_number += 1

        cur.close()
        con.close()

        return True

    def install_asigra(self):
        ret = True

        if os.path.exists("/asigra"):
            dssystem_pkg = None

            files = glob.glob("/asigra/DS-System_*/dssystem-*.txz")
            for f in files:
                dssystem_pkg = f

            if dssystem_pkg:
                with open("/tmp/dssystem_install.ini", "w") as f:
                    f.write("silentmode=yes\n")

                proc = Popen(
                    ['/usr/sbin/pkg', 'add', '-f', dssystem_pkg],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    close_fds=True,
                    env={'INSTALL_INI': '/tmp/dssystem_install.ini'}
                )
            else:
                ret = False

            output = (proc.communicate())[0].decode()
            if proc.returncode != 0:
                self.logger.error(output)
                self.logger.error('Failed to install dssystem package:\n{}'.format(output))
                ret = False

            if ret is not False:
                try:
                    os.chmod("/usr/local/etc/rc.d/dssystem", 0o555)
                    shutil.copyfile("/usr/local/etc/rc.d/dssystem", "/conf/base/etc/local/rc.d/dssystem")
                    os.chmod("/conf/base/etc/local/rc.d/dssystem", 0o555)

                except Exception:
                    self.logger.error("Failed to install dssystem rc.d script")
                    ret = False

        return ret

    def asigra_installed(self):
        if not os.path.exists(os.path.join(self.dssystem_path, "libasigraencmodule.so")):
            return False
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

        self.logger.debug("Checking to see if Asigra is installed")
        if not self.asigra_installed():
            self.logger.debug("Installing Asigra")
            self.install_asigra()

        self.logger.debug("Checking to see if database exists")
        if not self.asigra_database_exists():

            self.logger.debug("Creating database")
            self.asigra_database_create()

            self.logger.debug("Initializing database")
            self.asigra_database_init()

        else:
            self.logger.debug("Updating database")
            self.asigra_database_update()

        return True
