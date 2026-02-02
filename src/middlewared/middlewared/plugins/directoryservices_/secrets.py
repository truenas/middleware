import enum
import json
import os
import struct
import subprocess

from base64 import b64encode, b64decode
from middlewared.plugins.smb_.constants import SMBPath
from middlewared.service import Service
from middlewared.service_exception import CallError, MatchNotFound
from middlewared.utils.filter_list import filter_list
from middlewared.utils.tdb import (
    get_tdb_handle,
    TDBDataType,
    TDBOptions,
    TDBPathType,
)

SECRETS_FILE = os.path.join(SMBPath.PRIVATEDIR.path, 'secrets.tdb')
SECRETS_TDB_OPTIONS = TDBOptions(TDBPathType.CUSTOM, TDBDataType.BYTES)
SECRETS_CTDB_OPTIONS = TDBOptions(TDBPathType.PERSISTENT, TDBDataType.BYTES, True)
SECRETS_TDB_CONFIG = (SECRETS_FILE, SECRETS_TDB_OPTIONS)
SECRETS_CTDB_CONFIG = ('secrets.tdb', SECRETS_CTDB_OPTIONS)


# c.f. source3/include/secrets.h
class Secrets(enum.Enum):
    MACHINE_ACCT_PASS = 'SECRETS/$MACHINE.ACC'
    MACHINE_PASSWORD = 'SECRETS/MACHINE_PASSWORD'
    MACHINE_PASSWORD_PREV = 'SECRETS/MACHINE_PASSWORD.PREV'
    MACHINE_LAST_CHANGE_TIME = 'SECRETS/MACHINE_LAST_CHANGE_TIME'
    MACHINE_SEC_CHANNEL_TYPE = 'SECRETS/MACHINE_SEC_CHANNEL_TYPE'
    MACHINE_TRUST_ACCOUNT_NAME = 'SECRETS/SECRETS_MACHINE_TRUST_ACCOUNT_NAME'
    MACHINE_DOMAIN_INFO = 'SECRETS/MACHINE_DOMAIN_INFO'
    DOMTRUST_ACCT_PASS = 'SECRETS/$DOMTRUST.ACC'
    SALTING_PRINCIPAL = 'SECRETS/SALTING_PRINCIPAL'
    DOMAIN_SID = 'SECRETS/SID'
    SAM_SID = 'SAM/SID'
    PROTECT_IDS = 'SECRETS/PROTECT/IDS'
    DOMAIN_GUID = 'SECRETS/DOMGUID'
    SERVER_GUID = 'SECRETS/GUID'
    LDAP_BIND_PW = 'SECRETS/LDAP_BIND_PW'
    LDAP_IDMAP_SECRET = 'SECRETS/GENERIC/IDMAP_LDAP'
    LOCAL_SCHANNEL_KEY = 'SECRETS/LOCAL_SCHANNEL_KEY'
    AUTH_USER = 'SECRETS/AUTH_USER'
    AUTH_DOMAIN = 'SECRETS/AUTH_DOMAIN'
    AUTH_PASSWORD = 'SECRETS/AUTH_PASSWORD'


def _secrets_config(cluster: bool) -> tuple[str, TDBOptions]:
    return SECRETS_CTDB_CONFIG if cluster else SECRETS_TDB_CONFIG


def fetch_secrets_entry(key: str, cluster: bool) -> str:
    with get_tdb_handle(*_secrets_config(cluster)) as hdl:
        return hdl.get(key)


def store_secrets_entry(key: str, val: str, cluster: bool) -> str:
    with get_tdb_handle(*_secrets_config(cluster)) as hdl:
        return hdl.store(key, val)


def query_secrets_entries(filters: list, options: dict, cluster: bool) -> list:
    with get_tdb_handle(*_secrets_config(cluster)) as hdl:
        return filter_list(hdl.entries(), filters, options)


def sync_with_tdb_secrets() -> None:
    with get_tdb_handle(*_secrets_config(True)) as hdl:
        hdl.sync_with_tdb(SECRETS_FILE)


class DomainSecrets(Service):

    class Config:
        namespace = 'directoryservices.secrets'
        cli_private = True
        private = True

    def has_domain(self, domain):
        """
        Check whether running version of secrets.tdb has our machine account password
        """
        cluster = self.middleware.call_sync("smb.config")["stateful_failover"]
        try:
            fetch_secrets_entry(f"{Secrets.MACHINE_PASSWORD.value}/{domain.upper()}", cluster)
        except MatchNotFound:
            return False

        return True

    def last_password_change(self, domain):
        """
        Retrieve the last password change timestamp for the specified domain.
        Raises MatchNotFound if entry is not present in secrets.tdb
        """
        cluster = self.middleware.call_sync("smb.config")["stateful_failover"]
        encoded_change_ts = fetch_secrets_entry(
            f"{Secrets.MACHINE_LAST_CHANGE_TIME.value}/{domain.upper()}]", cluster
        )
        try:
            bytes_passwd_chng = b64decode(encoded_change_ts)
        except Exception:
            self.logger.warning("Failed to retrieve last password change time for domain "
                                "[%s] from domain secrets. Directory service functionality "
                                "may be impacted.", domain, exc_info=True)
            return None

        return struct.unpack("<L", bytes_passwd_chng)[0]

    def set_ipa_secret(self, domain, secret):
        # The stored secret in secrets.tdb and our kerberos keytab for SMB must be kept in-sync
        cluster = self.middleware.call_sync("smb.config")["stateful_failover"]
        store_secrets_entry(
            f'{Secrets.MACHINE_PASSWORD.value}/{domain.upper()}', b64encode(b"2\x00").decode(), cluster
        )

        # Password changed field must be initialized (but otherwise is not required)
        store_secrets_entry(
            f"{Secrets.MACHINE_LAST_CHANGE_TIME.value}/{domain.upper()}", b64encode(b"2\x00").decode(), cluster
        )

        setsecret = subprocess.run(
            ['net', 'changesecretpw', '-f', '-d', '5'],
            capture_output=True, check=False, input=secret
        )
        if setsecret.returncode != 0:
            raise CallError(f'Failed to set machine account secret: {setsecret.stdout.decode()}')

        # Ensure we back this info up into our sqlite database as well
        self.backup()

    def set_ldap_idmap_secret(self, domain, user_dn, secret):
        """
        Some idmap backends (ldap and rfc2307) store credentials in secrets.tdb.
        This method is used by idmap plugin to write the password.
        """
        cluster = self.middleware.call_sync("smb.config")["stateful_failover"]
        store_secrets_entry(
            f'{Secrets.LDAP_IDMAP_SECRET.value}_{domain.upper()}/{user_dn}',
            b64encode(secret.encode() + b'\x00').decode(), cluster
        )

    def get_ldap_idmap_secret(self, domain, user_dn):
        """
        Retrieve idmap secret for the specifed domain and user dn.
        """
        cluster = self.middleware.call_sync("smb.config")["stateful_failover"]
        return fetch_secrets_entry(f'{Secrets.LDAP_IDMAP_SECRET.value}_{domain.upper()}/{user_dn}', cluster)

    def get_machine_secret(self, domain):
        cluster = self.middleware.call_sync("smb.config")["stateful_failover"]
        return fetch_secrets_entry(f'{Secrets.MACHINE_PASSWORD.value}/{domain.upper()}', cluster)

    def get_salting_principal(self, realm):
        cluster = self.middleware.call_sync("smb.config")["stateful_failover"]
        return fetch_secrets_entry(f'{Secrets.SALTING_PRINCIPAL.value}/DES/{realm.upper()}', cluster)

    def dump(self):
        """
        Dump contents of secrets.tdb. Values are base64-encoded
        """
        cluster = self.middleware.call_sync("smb.config")["stateful_failover"]
        entries = query_secrets_entries([], {}, cluster)
        return {entry['key']: entry['value'] for entry in entries}

    def sync_to_ctdb(self):
        cluster = self.middleware.call_sync("smb.config")["stateful_failover"]
        if not cluster:
            raise CallError("Stateful failover is not enabled")

        if not self.middleware.call_sync('failover.is_single_master_node'):
            raise CallError("This may only be called by active controller")

        try:
            sync_with_tdb_secrets()
        except FileNotFoundError:
            self.logger.info("Local secrets file not found. Falling back to restore from database.")
            self.middleware.call_sync("directoryservices.secrets.restore")

    async def get_db_secrets(self):
        """
        Retrieve secrets that are stored currently in freenas-v1.db.
        """
        db = await self.middleware.call('datastore.config', 'services.cifs', {
            'prefix': 'cifs_srv_', 'select': ['id', 'secrets']
        })
        if not db['secrets']:
            return {'id': db['id']}

        try:
            secrets = json.loads(db['secrets'])
        except json.decoder.JSONDecodeError:
            self.logger.warning("Stored secrets are not valid JSON "
                                "a new backup of secrets should be generated.")
        return {'id': db['id']} | secrets

    async def backup(self):
        """
        store backup of secrets.tdb contents (keyed on current netbios name) in
        freenas-v1.db file.
        """
        failover_status = await self.middleware.call('failover.status')
        if failover_status not in ('SINGLE', 'MASTER'):
            self.logger.debug("Current failover status [%s]. Skipping secrets backup.",
                              failover_status)
            return

        netbios_name = (await self.middleware.call('smb.config'))['netbiosname']
        db_secrets = await self.get_db_secrets()
        id_ = db_secrets.pop('id')

        if not (secrets := (await self.middleware.call('directoryservices.secrets.dump'))):
            self.logger.warning("Unable to parse secrets")
            return

        db_secrets.update({f"{netbios_name.upper()}$": secrets})
        await self.middleware.call(
            'datastore.update',
            'services.cifs', id_,
            {'secrets': json.dumps(db_secrets)},
            {'prefix': 'cifs_srv_'}
        )

    async def restore(self, netbios_name=None):
        """ Restore the contents of secrets.tdb from a stored backup of the node.
        This is allowed on standby controller as it preps winbindd for failover. """
        if netbios_name is None:
            netbios_name = (await self.middleware.call('smb.config'))['netbiosname']

        db_secrets = await self.get_db_secrets()
        server_secrets = db_secrets.get(f"{netbios_name.upper()}$")
        if server_secrets is None:
            self.logger.warning("Unable to find stored secrets for [%s]. "
                                "Directory service functionality may be impacted.",
                                netbios_name)
            return False

        cluster = (await self.middleware.call('smb.config'))['stateful_failover']
        self.logger.debug('Restoring secrets.tdb for %s', netbios_name)
        for key, value in server_secrets.items():
            await self.middleware.run_in_thread(store_secrets_entry, key, value, cluster)

        return True
