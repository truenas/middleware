from middlewared.api import api_method
from middlewared.api.base import BaseModel
from middlewared.api.current import GroupEntry, UserEntry
from pydantic import Field, model_validator
from middlewared.service import Service, job
from middlewared.service_exception import CallError, MatchNotFound
from middlewared.utils.directoryservices.constants import (
    DSStatus, DSType
)
from middlewared.utils.nss.pwd import iterpw
from middlewared.utils.nss.grp import itergrp
from middlewared.utils.nss.nss_common import NssModule, NssError, NssReturnCode
from middlewared.plugins.idmap_.idmap_constants import IDType
from middlewared.plugins.idmap_.idmap_winbind import WBClient
from .util_cache import (
    DSCacheFill,
    insert_cache_entry,
    query_cache_entries,
    retrieve_cache_entry
)

from time import sleep
from typing import Literal, Self


dscache_idtype = Literal['USER', 'GROUP']


class DscachePrincipalInfo(BaseModel):
    idtype: dscache_idtype
    who: str | None = None
    id: int | None = None

    @model_validator(mode='after')
    def check_identifier(self) -> Self:
        if self.who is None and self.id is None:
            raise ValueError('who or id required')

        return self


class DscacheInsertArgs(BaseModel):
    idtype: dscache_idtype
    cache_entry: UserEntry | GroupEntry


class DscacheInsertResult(BaseModel):
    result: None


class DscacheRetrieveOptions(BaseModel):
    smb: bool = True


class DscacheRetrieveArgs(BaseModel):
    principal_info: DscachePrincipalInfo
    options: DscacheRetrieveOptions = Field(default=DscacheRetrieveOptions())


class DscacheRetrieveResult(BaseModel):
    result: UserEntry | GroupEntry | None


class DscacheQueryArgs(BaseModel):
    idtype: dscache_idtype = 'USER'
    filters: list = []
    options: dict = {}


class DscacheQueryResult(BaseModel):
    result: list[UserEntry | GroupEntry]


class DSCache(Service):

    class Config:
        namespace = 'directoryservices.cache'
        private = True

    @api_method(DscacheInsertArgs, DscacheInsertResult, private=True)
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

    @api_method(DscacheRetrieveArgs, DscacheRetrieveResult, private=True)
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
                    if data.get('who') is not None:
                        who = {'username': data['who']}
                    else:
                        who = {'uid': data.get('id')}

                    pwdobj = self.middleware.call_sync('user.get_user_obj', {
                        'get_groups': False, 'sid_info': options['smb']
                    } | who)
                    if options['smb'] and pwdobj['sid'] is None:
                        # This indicates that idmapping is significantly broken
                        return None

                    entry = self.middleware.call_sync('idmap.synthetic_user',
                                                      pwdobj, pwdobj['sid'])
                    if entry is None:
                        return None
                else:
                    if data.get('who') is not None:
                        who = {'groupname': data.get('who')}
                    else:
                        who = {'gid': data.get('id')}

                    grpobj = self.middleware.call_sync('group.get_group_obj', {'sid_info': options['smb']} | who)
                    if options['smb'] and grpobj['sid'] is None:
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

    @api_method(DscacheQueryArgs, DscacheQueryResult, private=True)
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
            }, {'smb': ds['type'] in (DSType.AD.value, DSType.IPA.value)})

            return [entry] if entry else []

        # options must be omitted to defer pagination logic to caller
        entries = query_cache_entries(IDType[id_type], filters, {})
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

            # only log every 10th iteration
            if waited % 10 == 0:
                job.set_progress(10, 'Waiting for domain to come online')
                self.logger.debug('Waiting for domain to come online')

            sleep(1)
            waited += 1

        raise CallError('Timed out while waiting for domain to come online')

    def idmap_online_check_wait_sssd(self, job):
        """
        SSSD reports a domain as online before it will _actually_ return results
        for NSS queries. This is because getpwent and getgrent iterate the SSSD
        cache rather than reaching out to remote server. Since we know that
        enumeration is enabled if this is called then we can use getpwent and getgrent
        calls to determine whether the domain is in a state where we can actually
        fill our caches. This does present some minor risk that our initial cache
        fill on SSSD join will be incomplete, but there is no easy way to check
        intern status of SSSD's cache fill and so getting some users and groups
        initially and then retrieving remainder on next scheduled refresh is
        a suitable compromise.
        """
        waited = 0
        has_users = has_groups = False

        while waited <= 60:
            try:
                if not has_users:
                    for pwd in iterpw(module=NssModule.SSS.name):
                        has_users = True
                        break

                if not has_groups:
                    for grp in itergrp(module=NssModule.SSS.name):
                        has_groups = True
                        break

            except NssError as exc:
                # After SSSD is first wired up the NSS module may take some
                # time to become available.
                if exc.return_code != NssReturnCode.UNAVAIL:
                    raise exc from None

                self.logger.debug('nss_sss is currently unavailable.')
                # insert a little more delay to avoid spamming sssd
                sleep(5)

            if has_users and has_groups:
                # allow SSSD a little more time to build cache
                sleep(5)
                return

            # only log every 10th iteration
            if waited % 10 == 0:
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

        if ds['status'] not in (DSStatus.HEALTHY.name, DSStatus.JOINING.name):
            self.logger.warning(
                'Unable to refresh [%s] cache, state is: %s',
                ds['type'], ds['status']
            )
            return

        dom_by_sid = None
        ds_type = DSType(ds['type'])
        match ds_type:
            case DSType.AD:
                self.idmap_online_check_wait_wbclient(job)
                domain_info = self.middleware.call_sync(
                    'idmap.query',
                    [["domain_info", "!=", None]],
                    {'extra': {'additional_information': ['DOMAIN_INFO']}}
                )
                dom_by_sid = {dom['domain_info']['sid']: dom for dom in domain_info}
            case DSType.IPA | DSType.LDAP:
                self.idmap_online_check_wait_sssd(job)
            case _:
                raise ValueError(f'{ds_type}: unexpected DSType')

        with DSCacheFill() as dc:
            job.set_progress(15, 'Filling cache')
            dc.fill_cache(job, ds_type, dom_by_sid)

    async def abort_refresh(self):
        cache_job = await self.middleware.call('core.get_jobs', [
            ['method', '=', 'directoryservices.cache.refresh_impl'],
            ['state', '=', 'RUNNING']
        ])
        if cache_job:
            await self.middleware.call('core.job_abort', cache_job[0]['id'])
