import asyncio
import errno
import wbclient

from middlewared.api import api_method
from middlewared.api.current import IdmapDomainClearIdmapCacheArgs, IdmapDomainClearIdmapCacheResult
from middlewared.service import CallError, Service, job, private, ValidationError, filterable_api_method
from middlewared.service_exception import MatchNotFound
from middlewared.utils.directoryservices.constants import DSType as DirectoryServiceType
from middlewared.plugins.account_.constants import CONTAINER_ROOT_UID
from middlewared.plugins.idmap_.idmap_constants import (
    BASE_SYNTHETIC_DATASTORE_ID, IDType, SID_LOCAL_USER_PREFIX, SID_LOCAL_GROUP_PREFIX
)
from middlewared.plugins.idmap_.idmap_winbind import (WBClient, WBCErr)
from middlewared.plugins.idmap_.idmap_sss import SSSClient
from middlewared.plugins.smb_.constants import SMBBuiltin
from middlewared.utils import filter_list
from middlewared.utils.sid import (
    get_domain_rid,
    BASE_RID_GROUP,
    BASE_RID_USER,
    DomainRid,
    WellKnownSid,
)
from middlewared.utils.tdb import (
    get_tdb_handle,
    TDBDataType,
    TDBOptions,
    TDBPathType,
)
try:
    from pysss_murmur import murmurhash3
except ImportError:
    murmurhash3 = None

WINBIND_IDMAP_FILE = '/var/run/samba-lock/gencache.tdb'
WINBIND_IDMAP_TDB_OPTIONS = TDBOptions(TDBPathType.CUSTOM, TDBDataType.BYTES)


def clear_winbind_cache():
    with get_tdb_handle(WINBIND_IDMAP_FILE, WINBIND_IDMAP_TDB_OPTIONS) as hdl:
        return hdl.clear()


class IdmapDomainService(Service):

    class Config:
        namespace = 'idmap'
        cli_private = True

    @filterable_api_method(private=True)
    async def query(self, filters, options):
        """ This is a temporary compatibility method to prevent breaking the UI during transition
        to the new directory services APIs """
        return filter_list([
            {
                'id': 1,
                'name': 'DS_TYPE_ACTIVEDIRECTORY',
                'range_low': 100000001,
                'range_high': 200000001,
                'idmap_backend': 'RID',
                'options': {},
                'certificate': None,
            },
            {
                'id': 2,
                'name': 'DS_TYPE_LDAP',
                'range_low': 100000001,
                'range_high': 200000001,
                'idmap_backend': 'LDAP',
                'options': {},
                'certificate': None,
            },
            {
                'id': 5,
                'name': 'DS_TYPE_DEFAULT_DOMAIN',
                'range_low': 90000001,
                'range_high': 100000000,
                'idmap_backend': 'TDB',
                'options': {},
                'certificate': None,
            },
        ], filters, options)

    def __wbclient_ctx(self, retry=True):
        """
        Wrapper around setting up a temporary winbindd client context
        If winbindd is stopped, then try to once to start it and if that
        fails, present reason to caller.
        """
        try:
            return WBClient()
        except wbclient.WBCError as e:
            if not retry or e.error_code != wbclient.WBC_ERR_WINBIND_NOT_AVAILABLE:
                raise e

        if not self.middleware.call_sync('systemdataset.sysdataset_path'):
            raise CallError(
                'Unexpected filesystem mounted in the system dataset path. '
                'This may indicate a failure to initialize the system dataset '
                'and may be resolved by reviewing and fixing errors in the system '
                'dataset configuration.', errno.EAGAIN
            )

        self.middleware.call_sync('service.control', 'START', 'idmap', {'silent': False}).wait_sync(raise_error=True)
        return self.__wbclient_ctx(False)

    @filterable_api_method(private=True)
    def known_domains(self, query_filters, query_options):
        try:
            entries = [entry.domain_info() for entry in WBClient().all_domains()]
        except wbclient.WBCError as e:
            match e.error_code:
                case wbclient.WBC_ERR_INVALID_RESPONSE:
                    # Our idmap domain is not AD and so this is not expected to succeed
                    return []
                case wbclient.WBC_ERR_WINBIND_NOT_AVAILABLE:
                    # winbindd process is stopped this may be in hot code path. Skip
                    return []
                case _:
                    raise

        return filter_list(entries, query_filters, query_options)

    @filterable_api_method(private=True)
    def online_status(self, query_filters, query_options):
        try:
            all_info = self.known_domains()
        except wbclient.WBCError as e:
            raise CallError(str(e), WBCErr[e.error_code], e.error_code)

        entries = [{
            'domain': dom_info['netbios_domain'],
            'online': dom_info['online']
        } for dom_info in all_info]

        return filter_list(entries, query_filters, query_options)

    @private
    def domain_info(self, domain):
        return WBClient().domain_info(domain)

    @private
    async def get_sssd_low_range(self, domain, sssd_config=None, seed=0xdeadbeef):
        """
        This is best effort attempt for SSSD compatibility. It will allocate low
        range for then initial slice in the SSSD environment. The SSSD allocation algorithm
        is non-deterministic. Domain SID string is converted to a 32-bit hashed value
        using murmurhash3 algorithm.

        The modulus of this value with the total number of available slices is used to
        pick the slice. This slice number is then used to calculate the low range for
        RID 0. With the default settings in SSSD this will be deterministic as long as
        the domain has less than 200,000 RIDs.
        """
        sid = (await self.middleware.call('idmap.domain_info', domain))['sid']
        sssd_config = {} if not sssd_config else sssd_config
        range_size = sssd_config.get('range_size', 200000)
        range_low = sssd_config.get('range_low', 10001)
        range_max = sssd_config.get('range_max', 2000200000)
        max_slices = (range_max - range_low) // range_size

        data = sid.encode()
        hash_ = murmurhash3(data, len(data), seed)

        return (hash_ % max_slices) * range_size + range_size

    @api_method(IdmapDomainClearIdmapCacheArgs, IdmapDomainClearIdmapCacheResult, roles=['DIRECTORY_SERVICE_WRITE'])
    @job(lock='clear_idmap_cache', lock_queue_size=1)
    async def clear_idmap_cache(self, job):
        """
        Stop samba, remove the winbindd_cache.tdb file, start samba, flush samba's cache.
        This should be performed after finalizing idmap changes.
        """
        smb_started = await self.middleware.call('service.started', 'cifs')
        await (await self.middleware.call('service.control', 'STOP', 'idmap')).wait(raise_error=True)

        try:
            await self.middleware.run_in_thread(clear_winbind_cache)

        except FileNotFoundError:
            self.logger.debug("Failed to remove winbindd_cache.tdb. File not found.")

        except Exception:
            self.logger.debug("Failed to remove winbindd_cache.tdb.", exc_info=True)

        await self.middleware.call('idmap.gencache.flush')

        await (await self.middleware.call('service.control', 'START', 'idmap')).wait(raise_error=True)
        if smb_started:
            await (await self.middleware.call('service.control', 'RESTART', 'cifs')).wait(raise_error=True)

    @private
    async def backend_options(self):
        """ legacy wrapper currently maintained to avoid breaking the UI """
        return {'AD': 'AD', 'RID': 'RID', 'LDAP': 'LDAP', 'RFC2307': 'RFC2307'}

    @private
    def convert_sids(self, sidlist):
        """
        Internal bulk conversion method Windows-style SIDs to Unix IDs (uid or gid)
        This ends up being a de-facto wrapper around wbcCtxSidsToUnixIds from
        libwbclient (single winbindd request), and so it is the preferred
        method of batch conversion.
        """
        if not sidlist:
            raise CallError("List of SIDS to convert must contain at least one entry")

        try:
            client = self.__wbclient_ctx()
        except wbclient.WBCError as e:
            raise CallError(str(e), WBCErr[e.error_code], e.error_code)

        mapped = {}
        unmapped = {}
        to_check = []

        server_sid = self.middleware.call_sync('smb.local_server_sid')
        netbiosname = self.middleware.call_sync('smb.config')['netbiosname']

        for sid in sidlist:
            try:
                entry = self.__local_sid_to_entry(server_sid, netbiosname, sid, client.separator)
            except (KeyError, ValidationError):
                # This is a Unix SID or a local SID, but account doesn't exist
                unmapped.update({sid: sid})
                continue

            if entry:
                mapped[sid] = entry
                continue

            to_check.append(sid)

        # First try to retrieve SIDs via SSSD since SSSD and
        # winbind are both running when we are joined to an IPA
        # domain. Former provides authoritative SID<->XID resolution
        # IPA accounts. The latter is authoritative for local accounts.
        if self.middleware.call_sync('directoryservices.status')['type'] == DirectoryServiceType.IPA.value:
            if to_check:
                sss_ctx = SSSClient()
                results = sss_ctx.sids_to_idmap_entries(to_check)
                mapped |= results['mapped']
                to_check = list(results['unmapped'].keys())

        if to_check:
            try:
                results = client.sids_to_idmap_entries(to_check)
            except wbclient.WBCError as e:
                raise CallError(str(e), WBCErr[e.error_code], e.error_code)

            mapped |= results['mapped']
            unmapped |= results['unmapped']

        return {'mapped': mapped, 'unmapped': unmapped}

    @private
    def convert_unixids(self, id_list):
        """
        Internal bulk conversion method for Unix IDs (uid or gid) to Windows-style
        SIDs. This ends up being a de-facto wrapper around wbcCtxUnixIdsToSids
        from libwbclient (single winbindd request), and so it is the preferred
        method of batch conversion.
        """
        output = {'mapped': {}, 'unmapped': {}}

        if not id_list:
            return output

        if self.middleware.call_sync('directoryservices.status')['type'] == DirectoryServiceType.IPA.value:

            try:
                dom_info = self.middleware.call_sync('directoryservices.connection.ipa_get_smb_domain_info')
            except Exception:
                dom_info = None

            if dom_info:
                sss_ctx = SSSClient()
                results = sss_ctx.users_and_groups_to_idmap_entries(id_list)
                if not results['unmapped']:
                    # short-circuit
                    return results

                output['mapped'] = results['mapped']
                id_list = []
                for entry in results['unmapped'].keys():
                    id_type, xid = entry.split(':')
                    xid = int(xid)

                    if xid >= dom_info['range_id_min'] and xid <= dom_info['range_id_max']:
                        # ID is provided by SSSD but does not have a SID allocated
                        # do not include in list to look up via winbind since
                        # we do not want to introduce potential for hanging for
                        # the winbind request timeout.
                        continue

                    id_list.append({
                        'id_type': 'USER' if id_type == 'UID' else 'GROUP',
                        'id': int(xid)
                    })

        if id_list:
            try:
                client = self.__wbclient_ctx()
                results = client.users_and_groups_to_idmap_entries(id_list)
            except wbclient.WBCError as e:
                raise CallError(str(e), WBCErr[e.error_code], e.error_code)

            output['mapped'] |= results['mapped']
            output['unmapped'] = results['unmapped']

        return output

    def __unixsid_to_entry(self, sid, separator):
        if not sid.startswith((SID_LOCAL_USER_PREFIX, SID_LOCAL_GROUP_PREFIX)):
            return None

        if sid.startswith(SID_LOCAL_USER_PREFIX):
            uid = int(sid[len(SID_LOCAL_USER_PREFIX):])
            u = self.middleware.call_sync('user.get_user_obj', {'uid': uid})
            return {
                'name': f'Unix User{separator}{u["pw_name"]}',
                'id': uid,
                'id_type': IDType.USER.name,
                'sid': sid
            }

        gid = int(sid[len(SID_LOCAL_GROUP_PREFIX):])
        g = self.middleware.call_sync('group.get_group_obj', {'gid': gid})
        return {
            'name': f'Unix Group{separator}{g["gr_name"]}',
            'id': gid,
            'id_type': IDType.GROUP.name,
            'sid': sid
        }

    def __local_sid_to_entry(self, server_sid, netbiosname, sid, separator):
        """
        Attempt to resolve SID to an ID entry without querying winbind or
        SSSD for it. This should be possible for local user accounts.
        """
        if (entry := self.__unixsid_to_entry(sid, separator)) is not None:
            return entry

        if not sid.startswith(server_sid):
            return None

        rid = get_domain_rid(sid)
        if rid == DomainRid.ADMINS:
            return {
                'name': f'{netbiosname}{separator}{SMBBuiltin.ADMINISTRATORS.nt_name}',
                'id': SMBBuiltin.ADMINISTRATORS.rid,
                'id_type': IDType.GROUP.name,
                'sid': sid,
            }
        elif rid == DomainRid.GUESTS:
            return {
                'name': f'{netbiosname}{separator}{SMBBuiltin.GUESTS.nt_name}',
                'id': SMBBuiltin.GUESTS.rid,
                'id_type': IDType.GROUP.name,
                'sid': sid,
            }
        elif rid > BASE_RID_GROUP:
            id_type = IDType.GROUP.name
            method = 'group.get_instance'
            xid_key = 'gid'
            name_key = 'name'
            db_id = rid - BASE_RID_GROUP
        elif rid > BASE_RID_USER:
            id_type = IDType.USER.name
            method = 'user.get_instance'
            xid_key = 'uid'
            name_key = 'username'
            db_id = rid - BASE_RID_USER
        else:
            # Log an error message and fall through to winbind or sssd to resolve it
            self.logger.warning('%s: unexpected local SID value', sid)
            return None

        entry = self.middleware.call_sync(method, db_id)

        return {
            'name': f'{netbiosname}{separator}{entry[name_key]}',
            'id': entry[xid_key],
            'id_type': id_type,
            'sid': sid
        }

    @filterable_api_method(private=True)
    async def builtins(self, filters, options):
        out = []
        idmap_backend = await self.middleware.call("smb.getparm", "idmap config * : backend", "GLOBAL")
        if idmap_backend != "tdb":
            """
            idmap_autorid and potentially other allocating idmap backends may be used for
            the default domain.
            """
            return []

        idmap_range = await self.middleware.call("smb.getparm", "idmap config * : range", "GLOBAL")
        low_range = int(idmap_range.split("-")[0].strip())
        for idx, sid_entry in enumerate(WellKnownSid):
            out.append({
                'name': sid_entry.name,
                'id': idx,
                'gid': low_range + 3 + idx,
                'sid': sid_entry.sid,
                'set': sid_entry.valid_for_mapping,
            })

        return filter_list(out, filters, options)

    @private
    async def id_to_name(self, xid, id_type):
        """
        Helper method to retrieve the name for the specified uid or gid. This method
        passes through user.query or group.query rather than user.get_user_obj or
        group.get_group_obj because explicit request for a uid / gid will trigger
        a directory service cache insertion if it does not already exist. This allows
        some lazily fill cache if enumeration for directory services is disabled.
        """
        idtype = IDType[id_type]
        idmap_timeout = 5.0

        match idtype:
            # IDType.BOTH is possible return by nss_winbind / nss_sss
            # and is special case when idmapping backend converts a SID
            # to both a user and a group. For most practical purposes it
            # can be treated interally as a group.
            case IDType.GROUP | IDType.BOTH:
                method = 'group.query'
                filters = [['gid', '=', xid]]
                key = 'group'
            case IDType.USER:
                method = 'user.query'
                filters = [['uid', '=', xid]]
                key = 'username'
            case _:
                raise CallError(f"Unsupported id_type: [{idtype.name}]")

        try:
            ret = await asyncio.wait_for(
                self.middleware.create_task(self.middleware.call(method, filters, {'get': True, 'order_by': [key]})),
                timeout=idmap_timeout
            )
            name = ret[key]
        except asyncio.TimeoutError:
            self.logger.debug(
                "timeout encountered while trying to convert %s id %d "
                "to name. This may indicate significant networking issue.",
                id_type.lower(), xid
            )
            name = None
        except MatchNotFound:
            name = None

        return name

    @private
    async def synthetic_user(self, passwd: dict, sid: str | None) -> dict | None:
        # local user, should be retrieved via user.query
        # with exception of our special synthetic account for the container root
        if passwd['source'] == 'LOCAL' and passwd['pw_uid'] != CONTAINER_ROOT_UID:
            return None

        return {
            'id': BASE_SYNTHETIC_DATASTORE_ID + passwd['pw_uid'],
            'uid': passwd['pw_uid'],
            'username': passwd['pw_name'],
            'unixhash': None,
            'smbhash': None,
            'home': passwd['pw_dir'],
            'shell': passwd['pw_shell'] or '/usr/bin/sh',  # An empty string as pw_shell means sh
            'full_name': passwd['pw_gecos'],
            'builtin': False,
            'smb': sid is not None,
            'userns_idmap': None,
            'group': {},
            'groups': [],
            'password_disabled': False,
            'ssh_password_enabled': False,
            'sshpubkey': None,
            'locked': False,
            'sudo_commands': [],
            'sudo_commands_nopasswd': [],
            'email': None,
            'local': False,
            'immutable': True,
            'twofactor_auth_configured': False,
            'sid': sid,
            'last_password_change': None,
            'password_age': None,
            'password_history': None,
            'password_change_required': False,
            'roles': [],
            'api_keys': [],
        }

    @private
    async def synthetic_group(self, grp, sid):
        if grp['source'] == 'LOCAL':
            # local group, should be retrieved via group.query
            return None

        return {
            'id': BASE_SYNTHETIC_DATASTORE_ID + grp['gr_gid'],
            'gid': grp['gr_gid'],
            'name': grp['gr_name'],
            'group': grp['gr_name'],
            'builtin': False,
            'sudo_commands': [],
            'sudo_commands_nopasswd': [],
            'users': [],
            'local': False,
            'roles': [],
            'smb': sid is not None,
            'userns_idmap': None,
            'sid': sid
        }
