from middlewared.schema import Str, Ref, Int, Dict, Bool, accepts
from middlewared.service import Service, job
from middlewared.service_exception import CallError, MatchNotFound
from middlewared.utils.directoryservices.constants import (
    DSStatus, DSType
)
from .all import get_enabled_ds

CACHES = [svc.value.upper() for svc in DSType]


class DSCache(Service):

    class Config:
        namespace = 'directoryservices.cache'
        private = True

    @accepts(
        Str('directory_service', required=True, enum=CACHES),
        Str('idtype', enum=['USER', 'GROUP'], required=True),
        Dict('cache_entry', additional_attrs=True),
    )
    async def insert(self, ds, idtype, entry):
        if idtype == "GROUP":
            id_key = "gid"
            name_key = "name"
        else:
            id_key = "uid"
            name_key = "username"

        ops = [
            {"action": "SET", "key": f'ID_{entry[id_key]}', "val": entry},
            {"action": "SET", "key": f'NAME_{entry[name_key]}', "val": entry}
        ]
        await self.middleware.call('tdb.batch_ops', {
            "name": f'{ds.lower()}_{idtype.lower()}',
            "ops": ops
        })
        return True

    @accepts(
        Str('directory_service', required=True, enum=CACHES),
        Dict(
            'principal_info',
            Str('idtype', enum=['USER', 'GROUP']),
            Str('who'),
            Int('id'),
        ),
        Dict(
            'options',
            Bool('synthesize', default=False),
            Bool('smb', default=False)
        )
    )
    async def retrieve(self, ds, data, options):
        who_str = data.get('who')
        who_id = data.get('id')
        if who_str is None and who_id is None:
            raise CallError("`who` or `id` entry is required to uniquely "
                            "identify the entry to be retrieved.")

        tdb_name = f'{ds.lower()}_{data["idtype"].lower()}'
        prefix = "NAME" if who_str else "ID"
        tdb_key = f'{prefix}_{who_str if who_str else who_id}'
        name_key = "username" if data['idtype'] == 'USER' else 'group'

        try:
            entry = await self.middleware.call("tdb.fetch", {"name": tdb_name, "key": tdb_key})
        except MatchNotFound:
            entry = None

        if not entry and options['synthesize']:
            """
            if cache lacks entry, create one from passwd / grp info,
            insert into cache and return synthesized value.
            user.get_user_obj and group.get_group_obj will raise KeyError if NSS lookup fails.
            """
            try:
                if data['idtype'] == 'USER':
                    if who_str is not None:
                        who = {'username': who_str}
                    else:
                        who = {'uid': who_id}

                    pwdobj = await self.middleware.call('user.get_user_obj', {
                        'get_groups': False, 'sid_info': True
                    } | who)
                    if pwdobj['sid'] is None:
                        # This indicates that idmapping is significantly broken
                        return None

                    entry = await self.middleware.call('idmap.synthetic_user',
                                                       ds.lower(), pwdobj, pwdobj['sid'])
                    if entry is None:
                        return None
                else:
                    if who_str is not None:
                        who = {'groupname': who_str}
                    else:
                        who = {'gid': who_id}

                    grpobj = await self.middleware.call('group.get_group_obj', {'sid_info': True} | who)
                    if grpobj['sid'] is None:
                        # This indicates that idmapping is significantly broken
                        return None

                    entry = await self.middleware.call('idmap.synthetic_group',
                                                       ds.lower(), grpobj, grpobj['sid'])
                    if entry is None:
                        return None

                await self.insert(ds, data['idtype'], entry)
                entry['nt_name'] = entry[name_key]
            except KeyError:
                entry = None

        elif not entry:
            raise KeyError(who_str if who_str else who_id)

        if entry and not options['smb']:
            entry['sid'] = None
            entry['nt_name'] = None

        if entry is not None:
            entry['roles'] = []

        return entry

    @accepts(
        Str('ds', required=True, enum=CACHES),
        Str('idtype', required=True, enum=["USER", "GROUP"]),
    )
    async def entries(self, ds, idtype):
        entries = await self.middleware.call('tdb.entries', {
            'name': f'{ds.lower()}_{idtype.lower()}',
            'query-filters': [('key', '^', 'ID')]
        })
        return [x['val'] for x in entries]

    @accepts(
        Str('objtype', enum=['USERS', 'GROUPS'], default='USERS'),
        Ref('query-filters'),
        Ref('query-options'),
    )
    async def query(self, objtype, filters, options):
        """
        Query User / Group cache with `query-filters` and `query-options`.

        `objtype`: 'USERS' or 'GROUPS'
        """
        ds_state = await self.middleware.call('directoryservices.get_state')
        enabled_ds = None
        extra = options.get("extra", {})
        get_smb = 'SMB' in extra.get('additional_information', [])

        is_name_check = bool(filters and len(filters) == 1 and filters[0][0] in ['username', 'name', 'group'])
        is_id_check = bool(filters and len(filters) == 1 and filters[0][0] in ['uid', 'gid'])

        for dstype, state in ds_state.items():
            if state != 'DISABLED':
                enabled_ds = dstype
                break

        if not enabled_ds:
            return []

        if (is_name_check or is_id_check) and filters[0][1] == '=':
            key = 'who' if is_name_check else 'id'
            entry = await self.retrieve(enabled_ds.upper(), {
                'idtype': objtype[:-1],
                key: filters[0][2],
            }, {'synthesize': True, 'smb': get_smb})

            return [entry] if entry else []

        entries = await self.entries(enabled_ds.upper(), objtype[:-1])
        if not get_smb:
            for entry in entries:
                entry['sid'] = None
                entry['nt_name'] = None

        return sorted(entries, key=lambda i: i['id'])

    @job(lock="dscache_refresh")
    def refresh(self, job):
        """
        This is called from a cronjob every 24 hours and when a user clicks on
        the UI button to 'rebuild directory service cache'.
        """
        if (enabled_ds := get_enabled_ds()) is None:
            # No enabled directory services
            return

        match enabled_ds.status:
            case DSStatus.HEALTHY:
                enabled_ds.fill_cache()
            case _:
                self.logger.debug(
                    'Unable to refresh [%s] cache, state is: %s',
                    enabled_ds.ds_type.name, enabled_ds.status.name
                )
