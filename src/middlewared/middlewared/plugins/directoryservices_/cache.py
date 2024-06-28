from middlewared.schema import Str, Ref, Int, Dict, Bool, accepts
from middlewared.service import Service, job
from middlewared.service_exception import CallError, MatchNotFound
from middlewared.utils.directoryservices.constants import (
    DSType
)
from middlewared.plugins.idmap_.idmap_constants import IDType
from middlewared.plugins.idmap_.idmap_winbind import WBClient
from .util_cache import (
    DSCacheFill,
    insert_cache_entry,
    query_cache_entries,
    retrieve_cache_entry
)

from time import sleep


class DSCache(Service):

    class Config:
        namespace = 'directoryservices.cache'
        private = True

    @accepts(
        Str('idtype', enum=['USER', 'GROUP'], required=True),
        Dict('cache_entry', additional_attrs=True),
    )
    def _insert(self, idtype, entry):
        """
        Internal method to insert an entry into cache. Only consumers should be in this
        plugin

        Raises:
            RuntimeError (tdb library error / corruption)
        """
        match (id_type := IDType[idtype]):
            case IDType.GROUP:
                insert_cache_entry(id_type, entry['gid'], entry['name'], entry)
            case IDType.USER:
                insert_cache_entry(id_type, entry['uid'], entry['username'], entry)
            case _:
                raise ValueError(f'{id_type}: unexpected ID type')

    @accepts(
        Dict(
            'principal_info',
            Str('idtype', enum=['USER', 'GROUP']),
            Str('who'),
            Int('id'),
        ),
        Dict(
            'options',
            Bool('smb', default=False)
        )
    )
    def _retrieve(self, data, options):
        """
        Internal method to retrieve an entry from cache. If the entry does not exist then
        a lookup via NSS will be attempted and if successful a cache entry will be generated.
        Only consumers should be in this plugin. Either `who` or `id` should be specified.

        Returns:
            user.query entry (successful user lookup)
            group.query entry (successful group lookup)
            None (lookup failure)

        Raises:
            RuntimeError (tdb library error)
            CallError (Idmap lookup failure -- unexpected)
        """
        try:
            entry = retrieve_cache_entry(IDType[data['idtype']], data.get('who'), data.get('id'))
        except MatchNotFound:
            entry = None

        if not entry:
            """
            If cache lacks entry, create one from passwd / grp info, insert into cache
            user.get_user_obj and group.get_group_obj will raise KeyError if NSS lookup fails.
            """
            try:
                if data['idtype'] == 'USER':
                    name_key = 'username'

                    if data.get('who') is not None:
                        who = {'username': data['who']}
                    else:
                        who = {'uid': data.get('id')}

                    pwdobj = self.middleware.call_sync('user.get_user_obj', {
                        'get_groups': False, 'sid_info': True
                    } | who)
                    if pwdobj['sid'] is None:
                        # This indicates that idmapping is significantly broken
                        return None

                    entry = self.middleware.call_sync('idmap.synthetic_user',
                                                      pwdobj, pwdobj['sid'])
                    if entry is None:
                        return None
                else:
                    name_key = 'group'
                    if data.get('who') is not None:
                        who = {'groupname': data.get('who')}
                    else:
                        who = {'gid': data.get('id')}

                    grpobj = self.middleware.call_sync('group.get_group_obj', {'sid_info': True} | who)
                    if grpobj['sid'] is None:
                        # This indicates that idmapping is significantly broken
                        return None

                    entry = self.middleware.call_sync('idmap.synthetic_group',
                                                      grpobj, grpobj['sid'])
                    if entry is None:
                        return None

                self._insert(data['idtype'], entry)
            except KeyError:
                entry = None

        if entry and not options['smb']:
            # caller has not requested SMB information and so we should strip it
            entry['sid'] = None

        if entry is not None:
            entry['roles'] = []

        return entry

    @accepts(
        Str('id_type', enum=['USER', 'GROUP'], default='USER'),
        Ref('query-filters'),
        Ref('query-options'),
    )
    def query(self, id_type, filters, options):
        """
        Query User / Group cache with `query-filters` and `query-options`.

        NOTE: only consumers for this endpoint should be user.query and group.query.
        query-options (apart from determining whether to include "SMB" information)
        are not evaluated here because user.query and group.query applies pagination
        on full results.
        """
        ds = self.middleware.call_sync('directoryservices.status')
        if ds['type'] is None:
            return []

        extra = options.get("extra", {})
        get_smb = 'SMB' in extra.get('additional_information', [])

        is_name_check = bool(filters and len(filters) == 1 and filters[0][0] in ['username', 'name', 'group'])
        is_id_check = bool(filters and len(filters) == 1 and filters[0][0] in ['uid', 'gid'])

        if (is_name_check or is_id_check) and filters[0][1] == '=':
            # Special case where explitly single user / group is being queried.
            # If it's not present in cache we will directly issue NSS request and
            # generate cache entry based on its results. This allows slowly building
            # a cache when user / group enumeration is disabled.
            key = 'who' if is_name_check else 'id'
            entry = self._retrieve({
                'idtype': id_type,
                key: filters[0][2],
            }, {'smb': get_smb})

            return [entry] if entry else []

        # options must be omitted to defer pagination logic to caller
        entries = query_cache_entries(IDType[id_type], filters, {})
        if not get_smb:
            for entry in entries:
                entry['sid'] = None

        return sorted(entries, key=lambda i: i['id'])

    def idmap_online_check_wait_wbclient(self, job):
        """
        Check internal winbind status report for the domain. We want to wait
        for the domain to come fully online before proceeding with cache fill
        to avoid spurious errors.
        """
        waited = 0
        client = WBClient()
        while waited <= 60:
            if client.domain_info()['online']:
                return

            job.set_progress(10, 'Waiting for domain to come online')
            self.logger.debug('Waiting for domain to come online')
            sleep(1)
            waited += 1

        raise CallError('Timed out while waiting for domain to come online')

    @job(lock="directoryservices_cache_fill", lock_queue_size=1)
    def refresh_impl(self, job):
        """
        Rebuild the directory services cache. This is performed in the following
        situations:

        1. User starts a directory service
        2. User triggers manually through API or webui
        3. Once every 24 hours via cronjob
        """

        ds = self.middleware.call_sync('directoryservices.status')
        if ds['type'] is None:
            return

        if ds['status'] not in ('HEALTHY', 'JOINING'):
            self.logger.warning(
                'Unable to refresh [%s] cache, state is: %s',
                ds['type'], ds['status']
            )
            return

        ds_type = DSType(ds['type'])
        if ds_type is DSType.AD:
            self.idmap_online_check_wait_wbclient(job)
            domain_info = self.middleware.call_sync(
                'idmap.query',
                [["domain_info", "!=", None]],
                {'extra': {'additional_information': ['DOMAIN_INFO']}}
            )
            dom_by_sid = {dom['domain_info']['sid']: dom for dom in domain_info}
        else:
            dom_by_sid = None

        with DSCacheFill() as dc:
            job.set_progress(15, 'Filling cache')
            dc.fill_cache(job, ds_type, dom_by_sid)

    async def abort_refresh(self):
        cache_job = await self.middleware.call('core.get_jobs', [
            ['method', '=', 'directoryservices.cache.refresh'],
            ['state', '=', 'RUNNING']
        ])
        if cache_job:
            await self.middleware.call('core.job_abort', cache_job[0]['id'])
