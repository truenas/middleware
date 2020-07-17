import enum
import json
import os
import struct
import tdb
import pickle
import pwd
import grp

from base64 import b64encode, b64decode
from middlewared.schema import accepts
from middlewared.service import Service, private
from middlewared.plugins.smb import SMBCmd, SMBPath
from middlewared.utils import filter_list, osc, run
from samba.dcerpc.messaging import MSG_WINBIND_OFFLINE, MSG_WINBIND_ONLINE

OS_TYPE_FREEBSD = 0x01
OS_TYPE_LINUX = 0x02
OS_FLAG = int(osc.IS_FREEBSD) + (int(osc.IS_LINUX) << 1)


class DSStatus(enum.Enum):
    DISABLED = enum.auto()
    FAULTED = MSG_WINBIND_OFFLINE
    LEAVING = enum.auto()
    JOINING = enum.auto()
    HEALTHY = MSG_WINBIND_ONLINE


class DSType(enum.Enum):
    AD = ('activedirectory', OS_TYPE_FREEBSD | OS_TYPE_LINUX)
    LDAP = ('ldap', OS_TYPE_FREEBSD | OS_TYPE_LINUX)
    NIS = ('nis', OS_TYPE_FREEBSD)

    def byname(ds_name):
        for ds in DSType:
            if ds.value[1] & OS_FLAG and ds.value[0] == ds_name:
                return ds

        return None


class SSL(enum.Enum):
    NOSSL = 'OFF'
    USESSL = 'ON'
    USESTARTTLS = 'START_TLS'


class SASL_Wrapping(enum.Enum):
    PLAIN = 'PLAIN'
    SIGN = 'SIGN'
    SEAL = 'SEAL'


class NSS_Info(enum.Enum):
    SFU = ('SFU', [DSType.AD])
    SFU20 = ('SFU20', [DSType.AD])
    RFC2307 = ('RFC2307', [DSType.AD, DSType.LDAP])
    RFC2307BIS = ('RFC2307BIS', [DSType.LDAP])


class DirectorySecrets(object):
    def __init__(self, **kwargs):
        self.flags = kwargs.get('flags', 0)
        self.logger = kwargs.get('logger')
        self.ha_mode = kwargs.get('ha_mode')
        self.tdb = None
        self.is_open = False

    def open_tdb(self):
        if self.ha_mode == "LEGACY":
            secret_path = f'{SMBPath.LEGACYPRIVATE.platform()}/secrets.tdb'
        else:
            secret_path = f'{SMBPath.PRIVATEDIR.platform()}/secrets.tdb'

        if os.path.isfile(secret_path):
            self.tdb = tdb.open(secret_path, self.flags)
        else:
            self.tdb = tdb.Tdb(secret_path, 0, tdb.DEFAULT, os.O_CREAT | os.O_RDWR)
        self.is_open = True

    def has_domain(self, domain):
        return True if self.tdb.get(f"SECRETS/MACHINE_PASSWORD/{domain.upper()}".encode()) else False

    def last_password_change(self, domain):
        bytes_passwd_chng = self.tdb.get(f"SECRETS/MACHINE_LAST_CHANGE_TIME/{domain.upper()}".encode())
        if not bytes_passwd_chng:
            self.logger.warning("Failed to retrieve last password change time for domain "
                                "[%s] from domain secrets. Directory service functionality "
                                "may be impacted.")
            return None

        passwd_chg_ts = struct.unpack("<L", bytes_passwd_chng)[0]
        return passwd_chg_ts

    def dump(self):
        ret = {}
        self.tdb.read_lock_all()
        for entry in self.tdb:
            ret.update({entry.decode(): (b64encode(self.tdb.get(entry))).decode()})
            self.logger.debug("entry: %s", ret[entry.decode()])

        self.tdb.read_unlock_all()
        return ret

    def restore(self, secrets):
        self.tdb.transaction_start()
        for k, v in secrets.items():
            tdb_key = k.encode()
            tdb_data = b64decode(v)
            try:
                self.tdb.store(tdb_key, tdb_data)
            except Exception:
                self.logger.warning("Failed to store tdb data. "
                                    "Cancelling transaction.",
                                    exc_info=True)
                self.tdb.transaction_cancel()
                return

        self.tdb.transaction_commit()

    def __enter__(self):
        self.open_tdb()
        return self

    def __exit__(self, typ, value, traceback):
        if self.is_open:
            self.tdb.close()


class DirectoryServices(Service):
    class Config:
        service = "directoryservices"

    @accepts()
    async def get_state(self):
        """
        `DISABLED` Directory Service is disabled.

        `FAULTED` Directory Service is enabled, but not HEALTHY. Review logs and generated alert
        messages to debug the issue causing the service to be in a FAULTED state.

        `LEAVING` Directory Service is in process of stopping.

        `JOINING` Directory Service is in process of starting.

        `HEALTHY` Directory Service is enabled, and last status check has passed.
        """
        try:
            return (await self.middleware.call('cache.get', 'DS_STATE'))
        except KeyError:
            ds_state = {}
            for srv in DSType:
                if not srv.value[1] & OS_FLAG:
                    continue

                try:
                    res = await self.middleware.call(f'{srv.value[0]}.started')
                    ds_state[srv.value[0]] = DSStatus.HEALTHY.name if res else DSStatus.DISABLED.name
                except Exception:
                    ds_state[srv.value[0]] = DSStatus.FAULTED.name

            await self.middleware.call('cache.put', 'DS_STATE', ds_state)
            return ds_state

    @private
    async def set_state(self, new):
        ds_state = {}
        for ds in DSType:
            if ds.value[1] & OS_FLAG:
                ds_state.update({ds.value[0]: DSStatus.DISABLED.name})

        ds_state.update(await self.get_state())
        ds_state.update(new)
        self.middleware.send_event('directoryservices.status', 'CHANGED', fields=ds_state)
        return await self.middleware.call('cache.put', 'DS_STATE', ds_state)

    @accepts()
    async def cache_refresh(self):
        return await self.middleware.call('dscache.refresh')

    @private
    async def dstype_choices(self):
        choices = []
        for ds in DSType:
            if ds.value[1] & OS_FLAG:
                choices.append(ds.value[0])

        return choices

    @private
    async def ssl_choices(self, dstype):
        return [] if DSType(dstype.lower()) == DSType.NIS else [x.value for x in list(SSL)]

    @private
    async def sasl_wrapping_choices(self, dstype):
        return [] if DSType(dstype.lower()) == DSType.NIS else [x.value for x in list(SASL_Wrapping)]

    @private
    async def nss_info_choices(self, dstype):
        ds = DSType(dstype.lower())
        ret = []
        if ds == DSType.NIS:
            return ret

        for x in list(NSS_Info):
            if ds in x.value[1]:
                ret.append(x.value[0])

        return ret

    @private
    def get_db_secrets(self):
        rv = {}
        db = self.middleware.call_sync('datastore.query',
                                       'services.cifs', [],
                                       {'prefix': 'cifs_srv_', 'get': True})

        rv.update({"id": db['id']})
        if db['secrets'] is None:
            return rv

        try:
            rv.update(json.loads(db['secrets']))
        except json.decoder.JSONDecodeError:
            self.logger.warning("Stored secrets are not valid JSON "
                                "a new backup of secrets should be generated.")
        return rv

    @private
    def backup_secrets(self):
        """
        Writes the current secrets database to the freenas config file.
        """
        ha_mode = self.middleware.call_sync('smb.get_smb_ha_mode')

        if ha_mode == "UNIFIED":
            if self.middleware.call_sync("failover.status") != "MASTER":
                self.logger.debug("Skipping secrets backup on standby controller.")
                return

            ngc = self.middleware.call_sync("network.configuratoin.config")
            netbios_name = ngc["hostname_virtual"]
        else:
            netbios_name = self.middleware.call_sync('smb.config')['netbiosname_local']

        db_secrets = self.get_db_secrets()
        id = db_secrets.pop('id')

        with DirectorySecrets(logger=self.logger, ha_mode=ha_mode) as s:
            secrets = s.dump()

        if not secrets:
            self.logger.warning("Unable to parse secrets")
            return

        db_secrets.update({f"{netbios_name.upper()}$": secrets})
        self.middleware.call_sync('datastore.update',
                                  'services.cifs', id,
                                  {'secrets': json.dumps(db_secrets)},
                                  {'prefix': 'cifs_srv_'})

    @private
    def restore_secrets(self, netbios_name=None):
        """
        Restores secrets from a backup copy in the TrueNAS config file. This should
        be used with caution because winbindd will automatically update machine account
        passwords at configurable intervals. There is a periodic TrueNAS check that
        automates this backup, but care should be taken before manually invoking restores.
        """
        ha_mode = self.middleware.call_sync('smb.get_smb_ha_mode')

        if ha_mode == "UNIFIED":
            if self.middleware.call_sync("failover.status") != "MASTER":
                self.logger.debug("Skipping secrets restore on standby controller.")
                return

            if netbios_name is None:
                ngc = self.middleware.call_sync("network.configuratoin.config")
                netbios_name = ngc["hostname_virtual"]

        elif netbios_name is None:
            netbios_name = self.middleware.call_sync('smb.config')['netbiosname_local']

        db_secrets = self.get_db_secrets()

        server_secrets = db_secrets.get(f"{netbios_name.upper()}$")
        if server_secrets is None:
            self.logger.warning("Unable to find stored secrets for [%]. "
                                "Directory service functionality may be impacted.",
                                netbios_name)
            return False

        with DirectorySecrets(logger=self.logger, ha_mode=ha_mode) as s:
            try:
                s.restore(server_secrets)
            except Exception:
                self.logger.warning("Failed to restore secrets for [%s]. "
                                    "Directory service functionality may be impacted.",
                                    netbios_name, exc_info=True)
                return False

        return True

    @private
    def secrets_has_domain(self, domain):
        """
        Simple check to see whether a particular domain is in the
        secrets file. Traversing a tdb file can set a tdb chainlock
        on it. It's better to just do a quick lookup of the
        single value.
        """
        ha_mode = self.middleware.call_sync('smb.get_smb_ha_mode')
        with DirectorySecrets(logger=self.logger, ha_mode=ha_mode) as s:
            rv = s.has_domain(domain)

        return rv

    @private
    def get_last_password_change(self, domain=None):
        """
        Returns unix timestamp of last password change according to
        the secrets.tdb (our current running configuration), and what
        we have in our database.
        """
        ha_mode = self.middleware.call_sync('smb.get_smb_ha_mode')
        smb_config = self.middleware.call_sync('smb.config')
        if domain is None:
            domain = smb_config['workgroup']

        with DirectorySecrets(logger=self.logger, ha_mode=ha_mode) as s:
            passwd_ts = s.last_password_change(domain)

        db_secrets = self.get_db_secrets()
        server_secrets = db_secrets.get(f"{smb_config['netbiosname_local']}$")
        if server_secrets is None:
            return {"dbconfig": None, "secrets": passwd_ts}

        stored_ts_bytes = server_secrets[f'SECRETS/MACHINE_LAST_CHANGE_TIME/{domain.upper()}']
        stored_ts = struct.unpack("<L", b64decode(stored_ts_bytes))[0]

        return {"dbconfig": stored_ts, "secrets": passwd_ts}

    @private
    def available_secrets(self):
        """
        Entries in the secrets backup are keyed according to machine account name,
        which in this case is the netbios name of server followed by a dollar sign ($).
        These are possible values to add as an argument to 'restore_secrets' so that
        the secrets.tdb can be restored to what it was prior to a netbios name change.
        This functionality is intended more as a support tool than for general-purpose
        use in case user has become somewhat inventive with troubleshooting steps
        and changing server names.
        """
        db_secrets = self.get_db_secrets()
        db_secrets.pop('id')
        return list(db_secrets.keys())

    @private
    async def initialize(self):
        """
        Ensure that secrets.tdb at a minimum exists. If it doesn't exist, try to restore
        from a backup stored in our config file. If this fails, try to use what
        auth info we have to recover the information. If we are in an LDAP
        environment with a samba schema in use, we just need to write the password into
        secrets.tdb.
        """
        ldap_conf = await self.middleware.call("ldap.config")
        ldap_enabled = ldap_conf['enable']
        ad_enabled = (await self.middleware.call("activedirectory.config"))['enable']
        workgroup = (await self.middleware.call("smb.config"))["workgroup"]

        if not ldap_enabled and not ad_enabled:
            return

        has_secrets = await self.middleware.call("directoryservices.secrets_has_domain", workgroup)

        if ad_enabled and not has_secrets:
            kerberos_method = await self.middleware.call("smb.getparm", "kerberos method", "GLOBAL")
            self.logger.warning("Domain secrets database does not exist. "
                                "Attempting to restore.")
            ok = await self.middleware.call("directoryservices.restore_secrets")
            if not ok:
                self.logger.warning("Failed to restore domain secrets database. "
                                    "Re-joining AD domain may be required.")

                if kerberos_method != "secrets and keytab":
                    self.logger.warning("Restoration of secrets database failed. "
                                        "Attempting to automatically re-join AD domain.")
                    try:
                        await self.middleware.call("activedirectory.start")
                    except Exception:
                        self.logger.warning("Failed to re-join active directory domain.",
                                            exc_info=True)

        elif ldap_enabled and not has_secrets and ldap_conf["has_samba_schema"]:
            self.logger.warning("LDAP SMB secrets database does not exist. "
                                "attempting to restore secrets from configuration file.")
            self.middleware.call("smb.store_ldap_admin_password")

        gencache_flush = await run([SMBCmd.NET.value, 'cache', 'flush'], check=False)
        if gencache_flush.returncode != 0:
            self.logger.warning("Failed to clear the SMB gencache after re-initializing "
                                "directory services: [%s]", gencache_flush.stderr.decode())


class DSCache(Service):

    class Config:
        private = True

    def get_uncached_user(self, username=None, uid=None):
        """
        Returns dictionary containing pwd_struct data for
        the specified user or uid. Will raise an exception
        if the user does not exist. This method is appropriate
        for user validation.
        """
        if username:
            u = pwd.getpwnam(username)
        elif uid is not None:
            u = pwd.getpwuid(uid)
        else:
            return {}
        return {
            'pw_name': u.pw_name,
            'pw_uid': u.pw_uid,
            'pw_gid': u.pw_gid,
            'pw_gecos': u.pw_gecos,
            'pw_dir': u.pw_dir,
            'pw_shell': u.pw_shell
        }

    def get_uncached_group(self, groupname=None, gid=None):
        """
        Returns dictionary containing grp_struct data for
        the specified group or gid. Will raise an exception
        if the group does not exist. This method is appropriate
        for group validation.
        """
        if groupname:
            g = grp.getgrnam(groupname)
        elif gid is not None:
            g = grp.getgrgid(gid)
        else:
            return {}
        return {
            'gr_name': g.gr_name,
            'gr_gid': g.gr_gid,
            'gr_mem': g.gr_mem
        }

    def initialize(self):
        ds_status = self.middleware.call_sync('directoryservices.get_state')
        for ds, status in ds_status.items():
            ds_type = DSType.byname(ds)
            if status != 'DISABLED':
                try:
                    with open(f'/var/db/system/.{ds_type.name}_cache_backup', 'rb') as f:
                        pickled_cache = pickle.load(f)

                    self.middleware.call_sync('cache.put',
                                              f'{ds_type.name}_cache',
                                              pickled_cache)
                except FileNotFoundError:
                    self.logger.debug('User cache file for [%s] is not present.', ds)

    def backup(self):
        ds_status = self.middleware.call_sync('directoryservices.get_state')
        for ds, status in ds_status.items():
            ds_type = DSType.byname(ds)
            if status != 'DISABLED':
                try:
                    ds_cache = self.middleware.call_sync('cache.get', f'{ds_type.name}_cache')
                    with open(f'/var/db/system/.{ds_type.name}_cache_backup', 'wb') as f:
                        pickle.dump(ds_cache, f)
                except KeyError:
                    self.logger.debug('No cache exists for directory service [%s].', ds)

    async def query(self, objtype='USERS', filters=None, options=None):
        """
        Query User / Group cache with `query-filters` and `query-options`.

        `objtype`: 'USERS' or 'GROUPS'

        Each directory service, when enabled, will generate a user and group cache using its
        respective 'fill_cache' method (ex: ldap.fill_cache). The cache entry is formatted
        as follows:

        The cache can be refreshed by calliing 'dscache.refresh'. The actual cache fill
        will run in the background (potentially for a long time). The exact duration of the
        fill process depends factors such as number of users and groups, and network
        performance. In environments with a large number of users (over a few thousand),
        administrators may consider disabling caching. In the case of active directory,
        the dscache will continue to be filled using entries from samba's gencache (the end
        result in this case will be that only users and groups actively accessing the share
        will be populated in UI dropdowns). In the case of other directory services, the
        users and groups will simply not appear in query results (UI features).

        """
        res = []
        ds_state = await self.middleware.call('directoryservices.get_state')

        is_name_check = bool(filters and len(filters) == 1 and filters[0][0] in ['username', 'groupname'])

        res.extend((await self.middleware.call(f'{objtype.lower()[:-1]}.query', filters, options)))

        for dstype, state in ds_state.items():
            if state != 'DISABLED':
                """
                Avoid iteration here if possible.  Use keys if single filter "=" and x in x=y is a
                username or groupname.
                """
                if is_name_check and filters[0][1] == '=':
                    cache = (await self.middleware.call(f'{dstype}.get_cache'))[objtype.lower()]
                    name = filters[0][2]
                    return [cache.get(name)] if cache.get(name) else []

                else:
                    res.extend(filter_list(
                        list((await self.middleware.call(f'{dstype}.get_cache'))[objtype.lower()].values()),
                        filters,
                        options
                    ))

        return res

    async def refresh(self):
        """
        This is called from a cronjob every 24 hours and when a user clicks on the
        UI button to 'rebuild directory service cache'.
        """
        ds_status = self.middleware.call_sync('directoryservices.get_state')
        for ds, status in ds_status.items():
            if status == 'HEALTHY':
                await self.middleware.call(f'{ds}.fill_cache', True)
            elif status != 'DISABLED':
                self.logger.debug('Unable to refresh [%s] cache, state is: %s' % (ds, status))

        await self.middleware.call('dscache.backup')


async def setup(middleware):
    middleware.event_register('directoryservices.status', 'Sent on directory service state changes.')
    """
    During initial boot, we need to wait for the system dataset to be imported.
    """
    if await middleware.call('system.ready'):
        await middleware.call('dscache.initialize')
