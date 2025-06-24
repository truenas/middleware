import enum
import os

from collections import defaultdict
from collections.abc import Iterable
from middlewared.utils.directoryservices.constants import (
    DSType
)
from middlewared.job import Job
from middlewared.utils import filter_list
from middlewared.utils.itertools import batched
from middlewared.utils.nss import pwd, grp
from middlewared.utils.nss.nss_common import NssModule
from middlewared.plugins.idmap_ import idmap_winbind, idmap_sss
from middlewared.plugins.idmap_.idmap_constants import (
    BASE_SYNTHETIC_DATASTORE_ID,
    IDType,
    MAX_REQUEST_LENGTH,
    SID_BUILTIN_PREFIX,
    SID_LOCAL_USER_PREFIX,
    SID_LOCAL_GROUP_PREFIX,
)
from middlewared.utils.tdb import (
    get_tdb_handle,
    TDBBatchAction,
    TDBBatchOperation,
    TDBPathType,
    TDBDataType,
    TDBHandle,
    TDBOptions
)
from threading import Lock
from uuid import uuid4

# Update progress of job every nth user / group, we expect possibly hundreds to
# a few thousand users and groups, but some edge cases where they number in
# tens of thousands. Percentage complete is not updated when generating
# progress messages because retrieving an approximate count of users and groups
# first is as expensive as generating the cache itself.
LOG_CACHE_ENTRY_INTERVAL = 10  # Update progress of job every nth user / group

TDB_LOCKS = defaultdict(Lock)

CACHE_OPTIONS = TDBOptions(TDBPathType.PERSISTENT, TDBDataType.JSON)


class DSCacheFile(enum.Enum):
    USER = 'directoryservice_cache_user'
    GROUP = 'directoryservice_cache_group'

    @property
    def path(self):
        return os.path.join(TDBPathType.PERSISTENT.value, f'{self.value}.tdb')


class DSCacheFill:
    """
    This class creates two temporary TDB files that contain cache entries for
    users and groups that contain same keys as results for user.query and group.query
    via the method `fill_cache()` once the cache is filled. The temporary TDB
    files are renamed over the current ones in-use by middleware. On context manager
    exit the handles on the TDB files are closed.

    NOTE: cache fill here is performed without taking on the USER_TDB_LOCK or
    GROUP_TDB_LOCK because the middleware caches will only be renamed over when fill
    is complete. This is to ensure relative continuity in cache results.
    """
    users_handle = None
    groups_handle = None

    def __enter__(self):
        file_prefix = f'directory_service_cache_tmp_{uuid4()}'
        self.users_handle = TDBHandle(f'{file_prefix}_user', CACHE_OPTIONS)
        self.groups_handle = TDBHandle(f'{file_prefix}_group', CACHE_OPTIONS)
        # Ensure we have clean initial state and restrictive permissions
        self.users_handle.clear()
        os.chmod(self.users_handle.full_path, 0o600)
        self.groups_handle.clear()
        os.chmod(self.groups_handle.full_path, 0o600)
        return self

    def __exit__(self, tp, value, tb):
        stored_exception = None
        try:
            if self.users_handle:
                self.users_handle.close()
        except Exception as exc:
            stored_exception = exc

        try:
            if self.groups_handle:
                self.groups_handle.close()
        except Exception as exc:
            stored_exception = exc

        if stored_exception:
            raise stored_exception

    def _commit(self):
        """
        Rename our temporary caches over ones in-use by middleware.

        This will be detected on next call to read / insert into cache.
        Stale handle will be closed and new one opened.
        """
        os.rename(self.users_handle.full_path, DSCacheFile.USER.path)
        os.rename(self.groups_handle.full_path, DSCacheFile.GROUP.path)

    def _add_sid_info_to_entries(
        self,
        idmap_ctx: idmap_winbind.WBClient | idmap_sss.SSSClient,
        nss_entries: list,
        dom_by_sid: dict
    ) -> list[dict]:
        """
        Add SID information to entries that NSS has returned. Dictionary
        entries in list `nss_entries` are modified in-place.

        `idmap_ctx` - is the winbind or sssd client handle to use to resolve
        posix accounts to SIDs

        `nss_entries` - list of posix accounts to look up

        `dom_by_sid` - mapping for trusted domains to provide idmap backend
        information for trusted domains. This is used to ensure that synthetic
        database IDs are unique and guaranteed to not change.

        Returns:
            Same list passed in as nss_entries
        """
        idmaps = idmap_ctx.users_and_groups_to_idmap_entries(nss_entries)
        to_remove = []

        for idx, entry in enumerate(nss_entries):
            unixkey = f'{IDType[entry["id_type"]].wbc_str()}:{entry["id"]}'
            if unixkey not in idmaps['mapped']:
                # not all users / groups in SSSD have SIDs
                # and so we'll leave them with a null SID
                # rather than removing from nss_entries
                continue

            idmap_entry = idmaps['mapped'][unixkey]
            if idmap_entry['sid'].startswith((SID_LOCAL_GROUP_PREFIX, SID_LOCAL_USER_PREFIX)):
                # There is a collision between local user / group and our AD one.
                # pop from cache
                to_remove.append(idx)
                continue

            if idmap_entry['sid'].startswith(SID_BUILTIN_PREFIX):
                # We don't want users to select auto-generated builtin groups
                to_remove.append(idx)
                continue

            entry['sid'] = idmap_entry['sid']
            entry['id_type'] = idmap_entry['id_type']
            if dom_by_sid:
                domain_sid = idmap_entry['sid'].rsplit('-', 1)[0]
                if domain_sid not in dom_by_sid:
                    # The administrator hasn't properly configured idmapping for this domain
                    # We won't include in cached accounts to dissuade from using the entry since
                    # the unix id assignment is not deterministic
                    to_remove.append(idx)
                    continue

                entry['domain_info'] = dom_by_sid[domain_sid]
            else:
                entry['domain_info'] = None

        to_remove.reverse()
        for idx in to_remove:
            nss_entries.pop(idx)

        return nss_entries

    def _get_entries_for_cache(
        self,
        idmap_ctx: idmap_winbind.WBClient | idmap_sss.SSSClient | None,
        nss_module: NssModule,
        entry_type: IDType,
        dom_by_sid: dict
    ) -> Iterable[dict]:
        """
        This method yields the users or groups in batches of 100 entries.
        If the directory service supports SIDs then these will also be added
        to the results.
        """
        match entry_type:
            case IDType.USER:
                nss_fn = pwd.iterpw
            case IDType.GROUP:
                nss_fn = grp.itergrp
            case _:
                raise ValueError(f'{entry_type}: unexpected `entry_type`')

        nss = nss_fn(module=nss_module.name)
        for entries in batched(nss, MAX_REQUEST_LENGTH):
            out = []
            for entry in entries:
                out.append({
                    'id': entry.pw_uid if entry_type is IDType.USER else entry.gr_gid,
                    'sid': None,
                    'nss': entry,
                    'id_type': entry_type.name,
                    'domain_info': None
                })

            # Depending on the directory sevice we may need to add SID
            # information to the NSS entries.
            if idmap_ctx is None:
                yield out
            else:
                yield self._add_sid_info_to_entries(idmap_ctx, out, dom_by_sid)

    def fill_cache(
        self,
        job: Job,
        ds_type: DSType,
        dom_by_sid: dict
    ) -> None:
        match ds_type:
            case DSType.AD:
                nss_module = NssModule.WINBIND
                idmap_ctx = idmap_winbind.WBClient()
            case DSType.LDAP:
                nss_module = NssModule.SSS
                idmap_ctx = None
            case DSType.IPA:
                nss_module = NssModule.SSS
                idmap_ctx = idmap_sss.SSSClient()
            case _:
                raise ValueError(f'{ds_type}: unknown DSType')

        user_count = 0
        group_count = 0

        job.set_progress(40, 'Preparing to add users to cache')

        # First grab batches of 100 entries
        for users in self._get_entries_for_cache(
            idmap_ctx,
            nss_module,
            IDType.USER,
            dom_by_sid
        ):
            # Now iterate members of 100 for insertion
            for u in users:
                if u['domain_info']:
                    id_type_both = u['domain_info']['idmap_backend'] in ('AUTORID', 'RID')
                else:
                    id_type_both = False

                user_data = u['nss']
                entry = {
                    'id': BASE_SYNTHETIC_DATASTORE_ID + user_data.pw_uid,
                    'uid': user_data.pw_uid,
                    'username': user_data.pw_name,
                    'unixhash': None,
                    'smbhash': None,
                    'group': {},
                    'home': user_data.pw_dir,
                    'shell': user_data.pw_shell or '/usr/bin/sh',  # An empty string as pw_shell means sh
                    'full_name': user_data.pw_gecos,
                    'builtin': False,
                    'email': None,
                    'password_disabled': False,
                    'locked': False,
                    'sudo_commands': [],
                    'sudo_commands_nopasswd': [],
                    'groups': [],
                    'sshpubkey': None,
                    'immutable': True,
                    'twofactor_auth_configured': False,
                    'local': False,
                    'id_type_both': id_type_both,
                    'smb': u['sid'] is not None,
                    'sid': u['sid'],
                    'roles': [],
                    'api_keys': [],
                    'last_password_change': None,
                    'password_age': None,
                    'password_history': None,
                    'password_change_required': False,
                }

                if user_count % LOG_CACHE_ENTRY_INTERVAL == 0:
                    job.set_progress(50, f'{user_data.pw_name}: adding user to cache. User count: {user_count}')

                # Store forward and reverse entries
                _tdb_add_entry(self.users_handle, user_data.pw_uid, user_data.pw_name, entry)
                user_count += 1

        job.set_progress(70, 'Preparing to add groups to cache')
        # First grab batches of 100 entries
        for groups in self._get_entries_for_cache(
            idmap_ctx,
            nss_module,
            IDType.GROUP,
            dom_by_sid
        ):
            for g in groups:
                if g['domain_info']:
                    id_type_both = g['domain_info']['idmap_backend'] in ('AUTORID', 'RID')
                else:
                    id_type_both = False

                group_data = g['nss']
                entry = {
                    'id': BASE_SYNTHETIC_DATASTORE_ID + group_data.gr_gid,
                    'gid': group_data.gr_gid,
                    'name': group_data.gr_name,
                    'group': group_data.gr_name,
                    'builtin': False,
                    'sudo_commands': [],
                    'sudo_commands_nopasswd': [],
                    'users': [],
                    'local': False,
                    'id_type_both': id_type_both,
                    'smb': g['sid'] is not None,
                    'sid': g['sid'],
                    'roles': []
                }

                if group_count % LOG_CACHE_ENTRY_INTERVAL == 0:
                    job.set_progress(80, f'{group_data.gr_name}: adding group to cache. Group count: {group_count}')

                _tdb_add_entry(self.groups_handle, group_data.gr_gid, group_data.gr_name, entry)
                group_count += 1

        job.set_progress(100, f'Cached {user_count} users and {group_count} groups.')
        self._commit()


def _tdb_add_entry(
    handle: TDBHandle,
    xid: int,
    name: str,
    entry: dict
) -> None:
    """
    Unlocked variant of adding cache entries. Should only be performed during initial cache fill.
    Performed without transaction as well because file will be removed in case of failure.

    Raises:
        RuntimeError via `tdb` library
    """
    handle.store(f'ID_{xid}', entry)
    handle.store(f'NAME_{name}', entry)


def insert_cache_entry(
    id_type: IDType,
    xid: int,
    name: str,
    entry: dict
) -> None:
    """
    This method is used to lazily insert cache entries that we don't already have.
    We perform under transaction lock since we don't want mismatched id and name entries

    Raises:
        RuntimeError via `tdb` library
    """
    with get_tdb_handle(DSCacheFile[id_type.name].value, CACHE_OPTIONS) as handle:
        handle.batch_op([
            TDBBatchOperation(action=TDBBatchAction.SET, key=f'ID_{xid}', value=entry),
            TDBBatchOperation(action=TDBBatchAction.SET, key=f'NAME_{xid}', value=entry),
        ])


def retrieve_cache_entry(
    id_type: IDType,
    name: str,
    xid: int
) -> None:
    """
    Retrieve cache entry under lock using stored handle. If both name and xid
    are specified, preference is given to xid.

    Raises:
        MatchNotFound
    """
    if xid is not None:
        key = f'ID_{xid}'
    else:
        key = f'NAME_{name}'

    with get_tdb_handle(DSCacheFile[id_type.name].value, CACHE_OPTIONS) as handle:
        return handle.get(key)


def query_cache_entries(
    id_type: IDType,
    filters: list,
    options: dict
) -> list:
    with get_tdb_handle(DSCacheFile[id_type.name].value, CACHE_OPTIONS) as handle:
        return filter_list(handle.entries(include_keys=False, key_prefix='ID_'), filters, options)
