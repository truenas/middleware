import os

from base64 import b64encode, b64decode
from middlewared.plugins.sysdataset import SYSDATASET_PATH
from middlewared.service import filterable_api_method, periodic, Service
from middlewared.service_exception import CallError, MatchNotFound
from middlewared.utils import filter_list
from middlewared.utils.security_descriptor import (
    share_acl_to_sd_bytes,
    sd_bytes_to_share_acl,
)
from middlewared.utils.tdb import (
    get_tdb_handle,
    TDBDataType,
    TDBOptions,
    TDBPathType,
)
from struct import pack

LOCAL_SHARE_INFO_FILE = os.path.join(SYSDATASET_PATH, 'samba4', 'share_info.tdb')
SHARE_INFO_TDB_OPTIONS = TDBOptions(TDBPathType.CUSTOM, TDBDataType.BYTES)
SHARE_INFO_VERSION_KEY = 'INFO/version'
SHARE_INFO_VERSION_DATA = b64encode(pack('<I', 3))


def fetch_share_acl(share_name: str) -> str:
    """ fetch base64-encoded NT ACL for SMB share """
    with get_tdb_handle(LOCAL_SHARE_INFO_FILE, SHARE_INFO_TDB_OPTIONS) as hdl:
        return hdl.get(f'SECDESC/{share_name.lower()}')


def set_version_share_info():
    with get_tdb_handle(LOCAL_SHARE_INFO_FILE, SHARE_INFO_TDB_OPTIONS) as hdl:
        hdl.store(SHARE_INFO_VERSION_KEY, SHARE_INFO_VERSION_DATA)


def store_share_acl(share_name: str, val: str) -> None:
    """ write base64-encoded NT ACL for SMB share to server running configuration """
    set_version_key = not os.path.exists(LOCAL_SHARE_INFO_FILE)
    with get_tdb_handle(LOCAL_SHARE_INFO_FILE, SHARE_INFO_TDB_OPTIONS) as hdl:
        if set_version_key:
            hdl.store(SHARE_INFO_VERSION_KEY, SHARE_INFO_VERSION_DATA)

        return hdl.store(f'SECDESC/{share_name.lower()}', val)


def remove_share_acl(share_name: str) -> None:
    """ remove ACL from share causing default entry of S-1-1-0 FULL_CONTROL """
    with get_tdb_handle(LOCAL_SHARE_INFO_FILE, SHARE_INFO_TDB_OPTIONS) as hdl:
        hdl.delete(f'SECDESC/{share_name.lower()}')


def dup_share_acl(src: str, dst: str) -> None:
    val = fetch_share_acl(src)
    store_share_acl(dst, val)


class ShareSec(Service):

    class Config:
        namespace = 'smb.sharesec'
        private = True

    @filterable_api_method(private=True)
    def entries(self, filters, options):
        # TDB file contains INFO/version key that we don't want to return
        try:
            with get_tdb_handle(LOCAL_SHARE_INFO_FILE, SHARE_INFO_TDB_OPTIONS) as hdl:
                return filter_list(
                    hdl.entries(),
                    filters + [['key', '^', 'SECDESC/']],
                    options
                )
        except FileNotFoundError:
            # File may not have been created yet or overzealous admin may have deleted
            return []

    def getacl(self, share_name):
        """
        View the ACL information for `share_name`. The share ACL is distinct from filesystem
        ACLs which can be viewed by calling `filesystem.getacl`.
        """
        if share_name.upper() == 'HOMES':
            share_filter = [['options.home', '=', True]]
        else:
            share_filter = [['name', 'C=', share_name]]

        try:
            self.middleware.call_sync(
                'sharing.smb.query', share_filter, {'get': True, 'select': ['home', 'name']}
            )
        except MatchNotFound as exc:
            raise CallError(f'{share_name}: share does not exist') from exc

        if not os.path.exists(LOCAL_SHARE_INFO_FILE):
            set_version_share_info()

        try:
            share_sd_bytes = b64decode(fetch_share_acl(share_name))
            share_acl = sd_bytes_to_share_acl(share_sd_bytes)
        except MatchNotFound:
            # Non-exist share ACL is treated as granting world FULL permissions
            share_acl = [{'ae_who_sid': 'S-1-1-0', 'ae_perm': 'FULL', 'ae_type': 'ALLOWED'}]

        return {'share_name': share_name, 'share_acl': share_acl}

    def setacl(self, data):
        """
        Set an ACL on `share_name`. Changes are written to samba's share_info.tdb file.
        This only impacts SMB sessions.

        `share_name` the name of the share

        `share_acl` a list of ACL entries (dictionaries) with the following keys:

        `ae_who_sid` who the ACL entry applies to expressed as a Windows SID

        `ae_perm` string representation of the permissions granted to the user or group.
        `FULL` grants read, write, execute, delete, write acl, and change owner.
        `CHANGE` grants read, write, execute, and delete.
        `READ` grants read and execute.

        `ae_type` can be ALLOWED or DENIED.
        """
        if data['share_name'].upper() == 'HOMES':
            share_filter = [['options.home', '=', True]]
        else:
            share_filter = [['name', 'C=', data['share_name']]]

        try:
            config_share = self.middleware.call_sync('sharing.smb.query', share_filter, {'get': True})
        except MatchNotFound as exc:
            raise CallError(f'{data["share_name"]}: share does not exist') from exc

        share_sd_bytes = b64encode(share_acl_to_sd_bytes(data['share_acl'])).decode()
        store_share_acl(data['share_name'], share_sd_bytes)

        self.middleware.call_sync(
            'datastore.update', 'sharing.cifs_share', config_share['id'],
            {'cifs_share_acl': share_sd_bytes}
        )

    def flush_share_info(self):
        """
        Write stored share acls to share_info.tdb. This should only be called
        if share_info.tdb contains default entries.
        """
        shares = self.middleware.call_sync('datastore.query', 'sharing.cifs_share', [], {'prefix': 'cifs_'})
        for share in shares:
            share_name = 'HOMES' if share['home'] else share['name']
            if share['share_acl'] and share['share_acl'].startswith('S-1-'):
                self.setacl({'share_name': share_name, 'share_acl': share['share_acl']})
            elif share['share_acl']:
                store_share_acl(share_name, share['share_acl'])

    @periodic(3600, run_on_start=False)
    def check_share_info_tdb(self):
        if not os.path.exists(LOCAL_SHARE_INFO_FILE):
            self.flush_share_info()
            return

        self.middleware.call_sync('smb.sharesec.synchronize_acls')

    async def synchronize_acls(self):
        """
        Synchronize the share ACL stored in the config database with Samba's running
        configuration as reflected in the share_info.tdb file.

        The only situation in which the configuration stored in the database will
        overwrite samba's running configuration is if share_info.tdb is empty. Samba
        fakes a single S-1-1-0:ALLOW/0x0/FULL entry in the absence of an entry for a
        share in share_info.tdb.
        """
        if not (entries := (await self.middleware.call('smb.sharesec.entries'))):
            # Current share_info.tdb doesn't exist or has no entries. If the config DB has any
            # entries we should flush them to running configuration.
            if await self.middleware.call('datastore.query', 'sharing.cifs_share'):
                await self.middleware.call('smb.sharesec.flush_share_info')
            return

        shares = await self.middleware.call('datastore.query', 'sharing.cifs_share', [], {'prefix': 'cifs_'})
        for s in shares:
            share_name = s['name'] if not s['home'] else 'homes'
            if not (share_acl := filter_list(entries, [['key', '=', f'SECDESC/{share_name.lower()}']])):
                continue

            if share_acl[0]['value'] != s['share_acl']:
                self.logger.debug('Updating stored copy of SMB share ACL on %s', share_name)
                await self.middleware.call(
                    'datastore.update',
                    'sharing.cifs_share',
                    s['id'],
                    {'cifs_share_acl': share_acl[0]['value']}
                )
