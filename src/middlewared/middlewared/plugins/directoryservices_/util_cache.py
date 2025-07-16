import enum
import os

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, timedelta
from middlewared.utils.directoryservices.constants import (
    DSType
)
from middlewared.job import Job
from middlewared.utils import filter_list
from middlewared.utils.itertools import batched
from middlewared.utils.nss import pwd, grp
from middlewared.utils.nss.nss_common import NssModule
from middlewared.utils.time_utils import utc_now
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

CACHE_OPTIONS = TDBOptions(TDBPathType.CUSTOM, TDBDataType.JSON)
CACHE_DIR = '/var/db/system/directory_services'

TRUENAS_CACHE_VERSION_KEY = 'TRUENAS_VERSION'
CACHE_EXPIRATION_KEY = 'CACHE_EXPIRATION'
CACHE_LIFETIME = timedelta(days=1)


class DSCacheFile(enum.Enum):
    USER = 'directoryservice_cache_user'
    GROUP = 'directoryservice_cache_group'

    @property
    def path(self):
        return os.path.join(CACHE_DIR, f'{self.value}.tdb')


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
        os.makedirs(CACHE_DIR, mode=0o700, exist_ok=True)
        file_prefix = f'directory_service_cache_tmp_{uuid4()}'
        self.users_handle = TDBHandle(os.path.join(CACHE_DIR, f'{file_prefix}_user.tdb'), CACHE_OPTIONS)
        self.groups_handle = TDBHandle(os.path.join(CACHE_DIR, f'{file_prefix}_group.tdb'), CACHE_OPTIONS)
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
    ) -> list[dict]:
        """
        Add SID information to entries that NSS has returned. Dictionary
        entries in list `nss_entries` are modified in-place.

        `idmap_ctx` - is the winbind or sssd client handle to use to resolve
        posix accounts to SIDs

        `nss_entries` - list of posix accounts to look up

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

        to_remove.reverse()
        for idx in to_remove:
            nss_entries.pop(idx)

        return nss_entries

    def _get_entries_for_cache(
        self,
        idmap_ctx: idmap_winbind.WBClient | idmap_sss.SSSClient | None,
        nss_module: NssModule,
        entry_type: IDType,
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
                })

            # Depending on the directory sevice we may need to add SID
            # information to the NSS entries.
            if idmap_ctx is None:
                yield out
            else:
                yield self._add_sid_info_to_entries(idmap_ctx, out)

    def fill_cache(
        self,
        job: Job,
        ds_type: DSType,
        truenas_version: str,
    ) -> None:
        """ Create and fill directory services cache based on the specified DSType
        params:
        -------
        job - middleware job object. Callers to the function should be a middleware job since it may be incredibly
            long-running.

        ds_type - The type of the enabled directory service. This is used to determine whether to use winbind client
            or sss client to speak to the domain in order to get SID information.

        truenas_version - output of system.version_short. Used for cache invalidation on middleware startup on version
            mismatch.


        returns:
        --------
        None - this method creates a new cache tdb and renames over existing one so that middleware never sees a
            partial cache file


        raises:
        -------
        ValueError - invalid DSType provided as `ds_type`.
        ValueError - IPA-only. SSSD failed to retrieve idmapping result. May indicate unhealthy domain.
        IOError - IPA-only. The SID operation is not supported. This is an unexpected and may indicate a significantly
            broken domain. Documented merely because it's a visible in the `pysss_nss_idmap.c` source.
        NssError - NSS module for directory service is in unhealthy state. This can result from join breaking while
            filling cache.
        WBCErr - AD-only. Winbind client error. This can also result from domain join breaking while filling cache.
        """
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
        expiration = utc_now(naive=False) + CACHE_LIFETIME

        job.set_progress(40, 'Preparing to add users to cache')
        for hdl in (self.users_handle, self.groups_handle):
            _tdb_add_version(hdl, truenas_version)
            _tdb_add_expiration(hdl, expiration)

        # First grab batches of 100 entries
        for users in self._get_entries_for_cache(
            idmap_ctx,
            nss_module,
            IDType.USER,
        ):
            # Now iterate members of 100 for insertion
            for u in users:
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
        ):
            for g in groups:
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


def _tdb_add_version(
    handle: TDBHandle,
    version: str
) -> None:
    """ Unlocked call to add version info to a TDB handle. """
    handle.store(TRUENAS_CACHE_VERSION_KEY, {'truenas_version': version})


def _tdb_add_expiration(handle: TDBHandle, timestamp: datetime) -> None:
    """ Add expiration timestamp to TDB handle. """
    handle.store(CACHE_EXPIRATION_KEY, {'expiration': timestamp})


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
    with get_tdb_handle(DSCacheFile[id_type.name].path, CACHE_OPTIONS) as handle:
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

    with get_tdb_handle(DSCacheFile[id_type.name].path, CACHE_OPTIONS) as handle:
        return handle.get(key)


def query_cache_entries(
    id_type: IDType,
    filters: list,
    options: dict
) -> list:
    with get_tdb_handle(DSCacheFile[id_type.name].path, CACHE_OPTIONS) as handle:
        return filter_list(handle.entries(include_keys=False, key_prefix='ID_'), filters, options)


def check_cache_version(truenas_version: str) -> None:
    """ Check that cache matches expected TrueNAS version and remove files if invalid. This should
    be called only during middleware startup. These files are not particularly valuable and so
    error handling here is to simply delete them. They will be replaced when directory services
    initialize after the system.ready event."""
    is_valid = True

    os.makedirs(CACHE_DIR, mode=0o700, exist_ok=True)

    for cache_file in DSCacheFile:
        try:
            with get_tdb_handle(cache_file.path, CACHE_OPTIONS) as hdl:
                try:
                    vers_data = hdl.get(TRUENAS_CACHE_VERSION_KEY)
                    if vers_data['truenas_version'] == truenas_version:
                        continue
                except Exception:
                    pass

                is_valid = False
                break
        except Exception:
            # Possibly a corrupted tdb file or garbage that was inserted into our persistent tdb directory.
            is_valid = False
            break

    if not is_valid:
        for cache_file in DSCacheFile:
            try:
                os.remove(cache_file.path)
            except Exception:
                pass


def check_cache_expired() -> bool:
    """ Check that cache files aren't expired. This prevents backend tasks from running
    unnecessary refresh jobs.

    Returns:
        True - one or more cache files is expired (or error encountered requiring refresh)
        False - no cache files are expired
    """
    now = utc_now(naive=False)

    for cache_file in DSCacheFile:
        if not os.path.exists(cache_file.path):
            # cache file is missing, we need to regenerate
            return True

        try:
            with get_tdb_handle(cache_file.path, CACHE_OPTIONS) as hdl:
                try:
                    vers_data = hdl.get(CACHE_EXPIRATION_KEY)
                    if vers_data['expiration'] > now:
                        # We have timestamp and it isn't expired. Move on to next file.
                        continue
                except Exception:
                    pass

                # If we get here, then the cache expiration key is missing or invalid
                # and so we fall through to flagging as expired so that the cache can be
                # regenerated.
        except Exception:
            # Possibly a corrupted tdb file or garbage that was inserted into our persistent tdb directory.
            pass

        return True

    # All cache files have expiration key and are not expired.
    return False


def expire_cache() -> None:
    """ Forcibly expire the directory services caches.
    NOTE: this is used in the CI pipeline for tests/directory_services. """

    # generate a timestamp in the past that's old enough to definitely trigger rebuild
    ts = utc_now(naive=True) - timedelta(days=2)

    for cache_file in DSCacheFile:
        with get_tdb_handle(cache_file.path, CACHE_OPTIONS) as hdl:
            _tdb_add_expiration(hdl, ts)
