import enum
import json
import os
import tdb

from base64 import b64encode, b64decode
from middlewared.schema import accepts
from middlewared.service import Service, private
from middlewared.plugins.smb import SMBCmd, SMBPath
from middlewared.utils import run
from samba.dcerpc.messaging import MSG_WINBIND_OFFLINE, MSG_WINBIND_ONLINE


class DSStatus(enum.Enum):
    DISABLED = enum.auto()
    FAULTED = MSG_WINBIND_OFFLINE
    LEAVING = enum.auto()
    JOINING = enum.auto()
    HEALTHY = MSG_WINBIND_ONLINE


class DSType(enum.Enum):
    AD = 'activedirectory'
    LDAP = 'ldap'
    NIS = 'nis'


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
        super(DirectorySecrets, self).__init__()
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
                try:
                    res = await self.middleware.call(f'{srv.value}.started')
                    ds_state[srv.value] = DSStatus.HEALTHY.name if res else DSStatus.DISABLED.name
                except Exception:
                    ds_state[srv.value] = DSStatus.FAULTED.name

            await self.middleware.call('cache.put', 'DS_STATE', ds_state)
            return ds_state

    @private
    async def set_state(self, new):
        ds_state = {
            'activedirectory': DSStatus.DISABLED.name,
            'ldap': DSStatus.DISABLED.name,
            'nis': DSStatus.DISABLED.name
        }
        ds_state.update(await self.get_state())
        ds_state.update(new)
        self.middleware.send_event('directoryservices.status', 'CHANGED', fields=ds_state)
        return await self.middleware.call('cache.put', 'DS_STATE', ds_state)

    @accepts()
    async def cache_refresh(self):
        return await self.middleware.call('dscache.refresh')

    @private
    async def dstype_choices(self):
        return [x.value.upper() for x in list(DSType)]

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
    def backup_secrets(self):
        ha_mode = self.middleware.call_sync('smb.get_smb_ha_mode')
        netbios_name = self.middleware.call_sync('smb.config')['netbiosname_local']
        db = self.middleware.call_sync('datastore.query',
                                       'services.cifs', [],
                                       {'prefix': 'cifs_srv_', 'get': True})

        if db['secrets'] is None:
            db_secrets = {}
        else:
            db_secrets = json.loads(db['secrets'])

        with DirectorySecrets(logger=self.logger, ha_mode=ha_mode) as s:
            secrets = s.dump()

        if not secrets:
            self.logger.warning("Unable to parse secrets")
            return

        db_secrets.update({netbios_name: secrets})
        self.middleware.call_sync('datastore.update',
                                  'services.cifs', 1,
                                  {'secrets': str(json.dumps(db_secrets))},
                                  {'prefix': 'cifs_srv_'})

    @private
    def restore_secrets(self, netbios_name=None):
        ha_mode = self.middleware.call_sync('smb.get_smb_ha_mode')

        if netbios_name is None:
            netbios_name = self.middleware.call_sync('smb.config')['netbiosname_local']

        db = self.middleware.call_sync('datastore.query',
                                       'services.cifs', [],
                                       {'prefix': 'cifs_srv_', 'get': True})

        db_secrets = json.loads(db['secrets'])
        server_secrets = db_secrets.get(netbios_name)
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
        ha_mode = self.middleware.call_sync('smb.get_smb_ha_mode')
        with DirectorySecrets(logger=self.logger, ha_mode=ha_mode) as s:
            rv = s.has_domain(domain)

        return rv

    @private
    def available_secrets(self):
        db = self.middleware.call_sync('datastore.query',
                                       'services.cifs', [],
                                       {'prefix': 'cifs_srv_', 'get': True})

        db_secrets = json.loads(db['secrets'])
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


def setup(middleware):
    middleware.event_register('directoryservices.status', 'Sent on directory service state changes.')
