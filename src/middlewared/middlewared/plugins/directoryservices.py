import enum
import json
import os
import struct
import tdb
import errno

from base64 import b64encode, b64decode
from middlewared.schema import accepts, Dict, List, OROperator, Ref, returns, Str
from middlewared.service import Service, private, job
from middlewared.plugins.smb import SMBCmd, SMBPath
from middlewared.service_exception import CallError
from middlewared.utils import run

DEFAULT_AD_CONF = {
    "id": 1,
    "bindname": "",
    "verbose_logging": False,
    "kerberos_principal": "",
    "kerberos_realm": None,
    "createcomputer": "",
    "disable_freenas_cache": False,
    "restrict_pam": False
}


class DSStatus(enum.Enum):
    DISABLED = enum.auto()
    FAULTED = 1028  # MSG_WINBIND_OFFLINE
    LEAVING = enum.auto()
    JOINING = enum.auto()
    HEALTHY = 1027  # MSG_WINBIND_ONLINE


class DSType(enum.Enum):
    AD = 'activedirectory'
    LDAP = 'ldap'


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
                                "may be impacted.", domain)
            return None

        passwd_chg_ts = struct.unpack("<L", bytes_passwd_chng)[0]
        return passwd_chg_ts

    def set_ldap_secret(self, domain, secret):
        self.tdb.transaction_start()
        tdb_key = f'SECRETS/GENERIC/IDMAP_LDAP_{domain.upper()}/{secret}'.encode()
        tdb_data = secret.encode() + b"\x00"
        try:
            self.tdb.store(tdb_key, tdb_data)
        except Exception as e:
            self.tdb.transaction_cancel()
            raise CallError(f"Failed to ldap secrets: {e}")

        self.tdb.transaction_commit()

    def dump(self):
        ret = {}
        self.tdb.read_lock_all()
        for entry in self.tdb:
            ret.update({entry.decode(): (b64encode(self.tdb.get(entry))).decode()})

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
        cli_namespace = "directory_service"

    @accepts()
    @returns(Dict(
        'directory_services_states',
        Ref('directoryservice_state', 'activedirectory'),
        Ref('directoryservice_state', 'ldap')
    ))
    async def get_state(self):
        """
        `DISABLED` Directory Service is disabled.

        `FAULTED` Directory Service is enabled, but not HEALTHY. Review logs and generated alert
        messages to debug the issue causing the service to be in a FAULTED state.

        `LEAVING` Directory Service is in process of stopping.

        `JOINING` Directory Service is in process of starting.

        `HEALTHY` Directory Service is enabled, and last status check has passed.
        """
        ha_mode = await self.middleware.call('smb.get_smb_ha_mode')
        svc = 'clustercache' if ha_mode == 'CLUSTERED' else 'cache'

        try:
            return await self.middleware.call(f'{svc}.get', 'DS_STATE')
        except KeyError:
            ds_state = {}
            for srv in DSType:
                try:
                    res = await self.middleware.call(f'{srv.value}.started')
                    ds_state[srv.value] = DSStatus.HEALTHY.name if res else DSStatus.DISABLED.name

                except CallError as e:
                    if e.errno == errno.EINVAL:
                        self.logger.warning('%s: setting service to DISABLED due to invalid config',
                                            srv.value.upper(), exc_info=True)
                        ds_state[srv.value] = DSStatus.DISABLED.name
                    else:
                        ds_state[srv.value] = DSStatus.FAULTED.name

                except Exception:
                    ds_state[srv.value] = DSStatus.FAULTED.name

            await self.middleware.call(f'{svc}.put', 'DS_STATE', ds_state, 60)
            return ds_state

        except CallError as e:
            if e.errno is not errno.ENXIO:
                raise

            self.logger.debug("Unable to determine directory services state while cluster is unhealthy")
            return {"activedirectory": "DISABLED", "ldap": "DISABLED"}

    @private
    async def set_state(self, new):
        ds_state = {
            'activedirectory': DSStatus.DISABLED.name,
            'ldap': DSStatus.DISABLED.name,
        }

        ha_mode = await self.middleware.call('smb.get_smb_ha_mode')
        svc = 'clustercache' if ha_mode == 'CLUSTERED' else 'cache'

        try:
            old_state = await self.middleware.call(f'{svc}.get', 'DS_STATE')
            ds_state.update(old_state)
        except KeyError:
            self.logger.trace("No previous DS_STATE exists. Lazy initializing for %s", new)

        ds_state.update(new)
        self.middleware.send_event('directoryservices.status', 'CHANGED', fields=ds_state)
        return await self.middleware.call(f'{svc}.put', 'DS_STATE', ds_state)

    @accepts()
    @job()
    async def cache_refresh(self, job):
        """
        This method refreshes the directory services cache for users and groups that is
        used as a backing for `user.query` and `group.query` methods. The first cache fill in
        an Active Directory domain may take a significant amount of time to complete and
        so it is performed as within a job. The most likely situation in which a user may
        desire to refresh the directory services cache is after new users or groups  to a remote
        directory server with the intention to have said users or groups appear in the
        results of the aforementioned account-related methods.

        A cache refresh is not required in order to use newly-added users and groups for in
        permissions and ACL related methods. Likewise, a cache refresh will not resolve issues
        with users being unable to authenticate to shares.
        """
        return await job.wrap(await self.middleware.call('dscache.refresh'))

    @private
    @returns(List(
        'ldap_ssl_choices', items=[
            Str('ldap_ssl_choice', enum=[x.value for x in list(SSL)], default=SSL.USESSL.value, register=True)
        ]
    ))
    async def ssl_choices(self, dstype):
        return [x.value for x in list(SSL)]

    @private
    @returns(List(
        'sasl_wrapping_choices', items=[
            Str('sasl_wrapping_choice', enum=[x.value for x in list(SASL_Wrapping)], register=True)
        ]
    ))
    async def sasl_wrapping_choices(self, dstype):
        return [x.value for x in list(SASL_Wrapping)]

    @private
    @returns(OROperator(
        List('ad_nss_choices', items=[Str(
            'nss_info_ad',
            enum=[x.value[0] for x in NSS_Info if DSType.AD in x.value[1]],
            default=NSS_Info.SFU.value[0],
            register=True
        )]),
        List('ldap_nss_choices', items=[Str(
            'nss_info_ldap',
            enum=[x.value[0] for x in NSS_Info if DSType.LDAP in x.value[1]],
            default=NSS_Info.RFC2307.value[0],
            register=True)
        ]),
        name='nss_info_choices'
    ))
    async def nss_info_choices(self, dstype):
        ds = DSType(dstype.lower())
        ret = []

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
        if ha_mode == "CLUSTERED":
            return

        elif ha_mode == "UNIFIED":
            failover_status = self.middleware.call_sync("failover.status")
            if failover_status != "MASTER":
                self.logger.debug("Current failover status [%s]. Skipping secrets backup.",
                                  failover_status)
                return

        netbios_name = self.middleware.call_sync('smb.config')['netbiosname']
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

        if ha_mode == "CLUSTERED":
            return True

        if ha_mode == "UNIFIED":
            failover_status = self.middleware.call_sync("failover.status")
            if failover_status != "MASTER":
                self.logger.debug("Current failover status [%s]. Skipping secrets backup.",
                                  failover_status)
                return

        if netbios_name is None:
            netbios_name = self.middleware.call_sync('smb.config')['netbiosname']

        db_secrets = self.get_db_secrets()

        server_secrets = db_secrets.get(f"{netbios_name.upper()}$")
        if server_secrets is None:
            self.logger.warning("Unable to find stored secrets for [%s]. "
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
        if ha_mode == 'CLUSTERED':
            # with clustered server we don't want misbehaving node to
            # potentially muck around with clustered secrets.
            return True

        with DirectorySecrets(logger=self.logger, ha_mode=ha_mode) as s:
            rv = s.has_domain(domain)

        return rv

    @private
    def set_ldap_secret(self, domain, secret):
        ha_mode = self.middleware.call_sync('smb.get_smb_ha_mode')
        with DirectorySecrets(logger=self.logger, ha_mode=ha_mode) as s:
            rv = s.set_ldap_secret(domain, secret)

        return rv

    @private
    def get_last_password_change(self, domain=None):
        """
        Returns unix timestamp of last password change according to
        the secrets.tdb (our current running configuration), and what
        we have in our database.
        """
        ha_mode = self.middleware.call_sync('smb.get_smb_ha_mode')
        if ha_mode == 'CLUSTERED':
            return

        smb_config = self.middleware.call_sync('smb.config')
        if domain is None:
            domain = smb_config['workgroup']

        with DirectorySecrets(logger=self.logger, ha_mode=ha_mode) as s:
            passwd_ts = s.last_password_change(domain)

        db_secrets = self.get_db_secrets()
        server_secrets = db_secrets.get(f"{smb_config['netbiosname_local'].upper()}$")
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
    async def initialize(self, data=None):
        """
        Ensure that secrets.tdb at a minimum exists. If it doesn't exist, try to restore
        from a backup stored in our config file. If this fails, try to use what
        auth info we have to recover the information. If we are in an LDAP
        environment with a samba schema in use, we just need to write the password into
        secrets.tdb.
        """
        if data is None:
            ldap_conf = await self.middleware.call("ldap.config")
            ldap_enabled = ldap_conf['enable']
            ad_enabled = (await self.middleware.call("activedirectory.config"))['enable']
        else:
            ldap_enabled = data['ldap']
            ad_enabled = data['activedirectory']
            if ldap_enabled:
                ldap_conf = await self.middleware.call("ldap.config")

        workgroup = (await self.middleware.call("smb.config"))["workgroup"]
        is_kerberized = ad_enabled

        if not ldap_enabled and not ad_enabled:
            return

        health_check = 'activedirectory.started' if ad_enabled else 'ldap.started'

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
            await self.middleware.call("smb.store_ldap_admin_password")

        if ldap_enabled and ldap_conf['kerberos_realm']:
            is_kerberized = True

        gencache_flush = await run([SMBCmd.NET.value, 'cache', 'flush'], check=False)
        if gencache_flush.returncode != 0:
            self.logger.warning("Failed to clear the SMB gencache after re-initializing "
                                "directory services: [%s]", gencache_flush.stderr.decode())

        if is_kerberized:
            try:
                await self.middleware.call('kerberos.start')
            except CallError:
                self.logger.warning("Failed to start kerberos after directory service "
                                    "initialization. Services dependent on kerberos may"
                                    "not work correctly.", exc_info=True)

        await self.middleware.call(health_check)

    @private
    @job(lock='ds_init', lock_queue_size=1)
    def setup(self, job):
        def restart_dependent_services():
            to_check = ['cifs', 'nfs']
            for svc in self.middleware.call_sync('service.query'):
                if not svc['enable'] or svc['service'] not in to_check:
                    continue

                self.middleware.call_sync('service.restart', svc['service'])

        config_in_progress = self.middleware.call_sync("core.get_jobs", [
            ["method", "=", "smb.configure"],
            ["state", "=", "RUNNING"]
        ])
        if config_in_progress:
            job.set_progress(0, "waiting for smb.configure to complete")
            wait_id = self.middleware.call_sync('core.job_wait', config_in_progress[0]['id'])
            wait_id.wait()

        ldap_enabled = self.middleware.call_sync('ldap.config')['enable']
        ad_enabled = self.middleware.call_sync('activedirectory.config')['enable']
        if not ldap_enabled and not ad_enabled:
            job.set_progress(100, "No directory services enabled.")
            return

        # Started methods will transition us from JOINING to HEALTHY
        # which allows the cache refresh to proceed
        if ad_enabled:
            self.middleware.call_sync('activedirectory.started')
        else:
            self.middleware.call_sync('ldap.started')

        job.set_progress(10, 'Refreshing cache'),
        cache_refresh = self.middleware.call_sync('dscache.refresh')
        cache_refresh.wait()

        job.set_progress(75, 'Restarting dependent services')
        restart_dependent_services()
        job.set_progress(100, 'Setup complete')


async def __init_directory_services(middleware, event_type, args):
    if args['id'] != 'ready':
        return

    await middleware.call('directoryservices.setup')


async def setup(middleware):
    middleware.event_subscribe('system', __init_directory_services)
    middleware.event_register('directoryservices.status', 'Sent on directory service state changes.')
