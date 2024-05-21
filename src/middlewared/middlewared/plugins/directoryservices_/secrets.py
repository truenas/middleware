import enum
import json
import struct

from base64 import b64encode, b64decode
from middlewared.service import Service
from middlewared.service_exception import MatchNotFound
from middlewared.plugins.tdb.utils import TDBError

SECRETS_FILE = '/var/db/system/samba4/private/secrets.tdb'


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
    LOCAL_SCHANNEL_KEY = 'SECRETS/LOCAL_SCHANNEL_KEY'
    AUTH_USER = 'SECRETS/AUTH_USER'
    AUTH_DOMAIN = 'SECRETS/AUTH_DOMAIN'
    AUTH_PASSWORD = 'SECRETS/AUTH_PASSWORD'


class DomainSecrets(Service):

    class Config:
        namespace = 'directoryservices.secrets'
        cli_private = True
        private = True

    tdb_options = {
        'backend': 'CUSTOM',
        'data_type': 'BYTES'
    }

    async def __fetch(self, key):
        return await self.middleware.call('tdb.fetch', {
            'name': SECRETS_FILE,
            'key': key,
            'tdb-options': self.tdb_options
        })

    async def __store(self, key, value):
        return await self.middleware.call('tdb.store', {
            'name': SECRETS_FILE,
            'key': key,
            'value': value,
            'tdb-options': self.tdb_options
        })

    async def __entries(self, filters, options):
        return await self.middleware.call('tdb.entries', {
            'name': SECRETS_FILE,
            'query-filters': filters,
            'query-options': options,
            'tdb-options': self.tdb_options
        })

    async def has_domain(self, domain):
        """
        Check whether running version of secrets.tdb has our machine account password
        """
        try:
            await self.__fetch(f"{Secrets.MACHINE_PASSWORD.value}/{domain.upper()}")
        except MatchNotFound:
            return False

        return True

    async def last_password_change(self, domain):
        """
        Retrieve the last password change timestamp for the specified domain.
        Raises MatchNotFound if entry is not present in secrets.tdb
        """
        encoded_change_ts = await self.__fetch(
            f"{Secrets.MACHINE_LAST_CHANGE_TIME.value}/{domain.upper()}"
        )
        try:
            bytes_passwd_chng = b64decode(encoded_change_ts)
        except Exception:
            self.logger.warning("Failed to retrieve last password change time for domain "
                                "[%s] from domain secrets. Directory service functionality "
                                "may be impacted.", domain, exc_info=True)
            return None

        return struct.unpack("<L", bytes_passwd_chng)[0]

    async def set_ldap_idmap_secret(self, domain, user_dn, secret):
        """
        Some idmap backends (ldap and rfc2307) store credentials in secrets.tdb.
        This method is used by idmap plugin to write the password.
        """
        await self.__store(
            f'SECRETS/GENERIC/IDMAP_LDAP_{domain.upper()}/{user_dn}',
            {'payload': b64encode(secret.encode() + b'\x00')}
        )

    async def get_ldap_idmap_secret(self, domain, user_dn):
        """
        Retrieve idmap secret for the specifed domain and user dn.
        """
        return await self.__fetch(f'SECRETS/GENERIC/IDMAP_LDAP_{domain.upper()}/{user_dn}')

    async def get_machine_secret(self, domain):
        return await self.__fetch(f'{Secrets.MACHINE_PASSWORD.value}/{domain.upper()}')

    async def get_salting_principal(self, realm):
        return await self.__fetch(f'{Secrets.SALTING_PRINCIPAL.value}/DES/{realm.upper()}')

    async def dump(self):
        """
        Dump contents of secrets.tdb. Values are base64-encoded
        """
        entries = await self.__entries([], {})
        return {entry['key']: entry['val'] for entry in entries}

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
        ha_mode = await self.middleware.call('smb.get_smb_ha_mode')
        if ha_mode == "UNIFIED":
            failover_status = await self.middleware.call("failover.status")
            if failover_status != "MASTER":
                self.logger.debug("Current failover status [%s]. Skipping secrets backup.",
                                  failover_status)
                return

        netbios_name = (await self.middleware.call('smb.config'))['netbiosname']
        db_secrets = await self.get_db_secrets()
        id_ = db_secrets.pop('id')

        if not (secrets := (await self.dump())):
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
        ha_mode = await self.middleware.call('smb.get_smb_ha_mode')
        if ha_mode == "UNIFIED":
            failover_status = await self.middleware.call("failover.status")
            if failover_status != "MASTER":
                self.logger.debug("Current failover status [%s]. Skipping secrets restore.",
                                  failover_status)
                return False

        if netbios_name is None:
            netbios_name = (await self.middleware.call('smb.config'))['netbiosname']

        db_secrets = await self.get_db_secrets()
        server_secrets = db_secrets.get(f"{netbios_name.upper()}$")
        if server_secrets is None:
            self.logger.warning("Unable to find stored secrets for [%s]. "
                                "Directory service functionality may be impacted.",
                                netbios_name)
            return False

        self.logger.debug('Restoring secrets.tdb for %s', netbios_name)
        for key, value in server_secrets.items():
            await self.__store(key, {'payload': value})

        return True
