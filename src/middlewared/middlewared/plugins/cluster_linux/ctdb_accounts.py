import json
import time

from middlewared.schema import accepts, Bool, Dict, Int, List, Patch, Str, LocalUsername
from middlewared.service import CRUDService, filterable, private, Service, ValidationErrors
from middlewared.service_exception import CallError, MatchNotFound, ValidationError
from middlewared.utils import filter_list
from middlewared.plugins.account import nt_password, pw_checkname
from middlewared.plugins.idmap_.utils import TRUENAS_IDMAP_MAX

ID_LWM = TRUENAS_IDMAP_MAX + 1


class CtdbAccountsService(Service):
    """
    This is a common wrapper for clustered users / groups into a single
    clustered key-value store. Contents are encrypted via clustered
    pwenc service prior to writes, and decrypted during reads.
    """

    class Config:
        namespace = 'ctdb.accounts.general'
        private = True

    tdb_options = {
        "cluster": True,
        "data_type": "STRING"
    }

    async def __entry_decode(self, val, is_json):
        decoded = await self.middleware.call('clpwenc.decrypt', val)
        data = json.loads(decoded) if is_json else decoded
        return data

    async def __entry_encode(self, val, is_json):
        data = json.dumps(val) if is_json else val
        return await self.middleware.call('clpwenc.encrypt', data)

    async def entries(self, filters, options):
        tdb_entries = await self.middleware.call('tdb.entries', {
            'name': 'truenas_accounts',
            'tdb-options': self.tdb_options
        })
        converted = []
        for entry in tdb_entries:
            converted.append(await self.__entry_decode(entry['val'], True))

        return filter_list(converted, filters, options)

    async def fetch(self, key, is_json=True):
        try:
            encoded_val = await self.middleware.call('tdb.fetch', {
                'name': 'truenas_accounts',
                'tdb-options': self.tdb_options,
                'key': key
            })
        except MatchNotFound:
            raise KeyError(key)

        return await self.__entry_decode(encoded_val, is_json)

    async def store(self, key, value, is_json=True):
        encoded_val = await self.__entry_encode(value, is_json)

        await self.middleware.call('tdb.store', {
            'name': 'truenas_accounts',
            'key': key,
            'value': {'payload': encoded_val},
            'tdb-options': self.tdb_options
        })

    async def remove(self, key):
        await self.middleware.call('tdb.remove', {
            'name': 'truenas_accounts',
            'key': key,
            'tdb-options': self.tdb_options
        })

    async def batch_ops(self, ops):
        # Perform a series of operations under a transaction lock
        # this is useful when atomically deleting user
        for op in ops:
            if 'val' not in op:
                continue

            op['val'] = await self.__entry_encode(op['val'], True)

        retrieved = await self.middleware.call('tdb.batch_ops', {
            'name': 'truenas_accounts',
            'ops': ops,
            'tdb-options': self.tdb_options
        })

        return [await self.__entry_decode(x) for x in retrieved]

    async def remote_op_recv(self, data):
        if data['action'] == 'RELOAD':
            await self.middleware.call('etc.generate', 'user')
        elif data['action'] == 'VALIDATE':
            for entry in data['entries']:
                if entry['id_type'] == 'USER':
                    method = 'user.get_user_obj'
                    key = 'username'
                    id_key = 'pw_uid'
                else:
                    method = 'group.get_group_obj'
                    key = 'groupname'
                    id_key = 'gr_gid'

                try:
                    res = await self.middleware.call(method, {key: entry['name']})
                    msg = f'{entry["name"]}: cluster {key} collides with existing '
                    msg += f'local {entry["id_type"].lower()} with an id of {res[id_key]}'
                    self.logger.error(msg)
                    raise ValidationError('ctdb.accounts.general.remote_op_recv', msg)

                except KeyError:
                    pass

    async def remote_op_send(self, data):
        # Currently this doesn't hit our timeout for clustered events
        # in VMs. If we start hitting timeouts, gluster.localevents.send
        # should be converted to a job or this method should be converted
        # to use the cluster jobs framework.
        config = await self.middleware.call('ctdb.root_dir.config')
        onnode = await self.middleware.call('gluster.localevents.send', {
            'event': 'CLUSTER_ACCOUNT',
            'name': config['volume_name'],
            'forward': True
        } | data)
        await onnode.wait(raise_error=True)


class ClusterUserService(CRUDService):

    class Config:
        namespace = 'cluster.accounts.user'
        cli_namespace = 'cluster.accounts.user'

    entry_keys = ['uid', 'gid', 'username', 'smbhash', 'full_name', 'locked']

    async def __set_password(self, data):
        password = data.pop('password')
        data['smbhash'] = f'{data["username"]}:{data["uid"]}:{"X" * 32}'
        data['smbhash'] += f':{nt_password(password)}:[U         ]:LCT-{int(time.time()):X}:'

    @filterable
    async def query(self, filters, options):
        entries = await self.middleware.call(
            'ctdb.accounts.general.entries',
            [['entry_type', '=', 'USER']],
            {'select': self.entry_keys.copy()}
        )
        return filter_list(entries, filters, options)

    @accepts(Dict(
        'ctdb_account_user',
        LocalUsername('username', required=True),
        Str('full_name', required=True),
        Str('password', private=True, required=True),
        Bool('locked', default=False),
        register=True
    ))
    async def create(self, data):
        """
        WARNING: clustering APIs are not intended for 3rd-party consumption and may result
        in a misconfigured SCALE cluster, production outage, or data loss.

        Create a new clustered SMB user. Supported keys are:

        `username` - Name of user. Case-insensitve, must be unique
        `full_name` - More descriptive name of user.
        `password` - Password for SMB authentication
        `locked` - Whether user should be locked (prevent SMB access)

        These users will not have home directories, shell access, and will
        have password disabled for non-SMB access. A new group will automatically
        be added with a name that mirrors the clustered user, and will be
        set as the user's primary group. UID and GID will be automatically
        allocated and may not be changed.
        """
        verrors = ValidationErrors()
        existing_users = await self.query([], {'order_by': ['-uid']})

        data['username'] = data['username'].lower()
        if filter_list(existing_users, [['username', '=', data['username']]]):
            verrors.add(
                'cluster_accounts_user_create.username'
                f'{data["username"]}: username already in use. Usernames '
                'for clustered users are case-insensitive'
            )
        else:
            try:
                await self.middleware.call('ctdb.accounts.general.remote_op_send', {
                    'action': 'VALIDATE',
                    'entries': [
                        {'id_type': 'USER', 'name': data['username']},
                        {'id_type': 'GROUP', 'name': data['username']}
                    ]
                })
            except ValidationError as e:
                #  sample url: http://cl3.nanny.goat:6000/_clusterevents
                url, msg = e.errmsg.split('|', 1)
                hostname = url.rsplit(':', 1)[0].split('http://')[1]
                verrors.add('cluster_accounts_user_create.username', f'{msg.strip()} on peer {hostname}')

            except Exception:
                self.logger.error('%s: validation of username failed.', data['username'], exc_info=True)
                verrors.add(
                    'cluster_accounts_user_create.username',
                    f'{data["username"]}: username already in use on remote node. '
                    'Usernames for clustered users are case-insensitive'
                )

        verrors.check()

        data['uid'] = existing_users[0]['uid'] + 1 if existing_users else ID_LWM
        await self.__set_password(data)

        group = await self.middleware.call('cluster.accounts.group.create_internal', {
            'group': data['username'],
            'users': [data['uid']],
            'internal': True
        })
        data['gid'] = group['gid']
        group_key = f'GROUP{group["gid"]}'
        user_key = f'USER{data["uid"]}'

        batch_ops = [
            {'action': 'SET', 'key': group_key, 'val': group | {'entry_type': 'GROUP'}},
            {'action': 'SET', 'key': user_key, 'val': data | {'entry_type': 'USER'}},
        ]

        try:
            await self.middleware.call('ctdb.accounts.general.batch_ops', batch_ops)
        except Exception as err:
            # Encountered issue, delete any keys we might have written
            for key in (group_key, user_key):
                try:
                    await self.middleware.call('ctdb.accounts.general.remove', key)
                except Exception:
                    pass

            raise err

        # we need to generate users before synchronizing passdb
        await self.middleware.call('etc.generate', 'user')
        pdb_job = await self.middleware.call('smb.synchronize_passdb')
        await pdb_job.wait()

        await self.middleware.call('ctdb.accounts.general.remote_op_send', {'action': 'RELOAD'})
        return data

    @accepts(
        Int('uid', required=True),
        Patch(
            'ctdb_account_user',
            'ctdb_account_user_update',
            ('attr', {'update': True}),
        )
    )
    async def update(self, uid, data):
        """
        WARNING: clustering APIs are not intended for 3rd-party consumption and may result
        in a misconfigured SCALE cluster, production outage, or data loss.

        Update a clustered user by `uid`.
        """
        old = await self.middleware.call('ctdb.accounts.general.fetch', f'USER{uid}')

        verrors = ValidationErrors()
        if (new_username := data.get('username')) and new_username != old['username']:
            if await self.query([['username', '=', new_username]]):
                verrors.add(
                    'cluster_accounts_user_create.username',
                    f'{new_username}: username already in use. Usernames '
                    'for clustered users are case-insensitive'
                )
            else:
                try:
                    await self.middleware.call('ctdb.accounts.general.remote_op_send', {
                        'action': 'VALIDATE',
                        'entries': [{'id_type': 'USER', 'name': data['username']}]
                    })
                except ValidationError as e:
                    #  sample url: http://cl3.nanny.goat:6000/_clusterevents
                    url, msg = e.errmsg.split('|', 1)
                    hostname = url.rsplit(':', 1)[0].split('http://')[1]
                    verrors.add('cluster_accounts_user_update.username', f'{msg.strip()} on peer {hostname}')
                except Exception:
                    self.logger.error('%s: validation of username failed.', data['username'], exc_info=True)
                    verrors.add(
                        'cluster_accounts_user_update.username',
                        f'{data["username"]}: username already in use on remote node. '
                        'Usernames for clustered users are case-insensitive'
                    )

        verrors.check()
        if data.get('password'):
            await self.__set_password(data)

        new = old | data
        await self.middleware.call('ctdb.accounts.general.store', f'USER{uid}', new)

        await self.middleware.call('etc.generate', 'user')
        pdb_job = await self.middleware.call('smb.synchronize_passdb')
        await pdb_job.wait()

        await self.middleware.call('ctdb.accounts.general.remote_op_send', {'action': 'RELOAD'})
        new.pop('entry_type')
        return new

    @accepts(Int('uid', required=True))
    async def delete(self, uid):
        """
        WARNING: clustering APIs are not intended for 3rd-party consumption and may result
        in a misconfigured SCALE cluster, production outage, or data loss.

        Delete a clustered user by `uid`
        """
        old = await self.middleware.call('ctdb.accounts.general.fetch', f'USER{uid}')

        batch_ops = [
            {'action': 'DEL', 'key': f'USER{uid}'},
            {'action': 'DEL', 'key': f'GROUP{old["gid"]}'},
        ]
        groups = await self.middleware.call(
            'cluster.accounts.group.query',
            [['users', 'rin', uid], ['internal', '=', False]]
        )
        for group in groups:
            group['users'].remove(uid)
            batch_ops.append({'action': 'SET', 'key': f'GROUP{group["gid"]}', 'val': group | {'entry_type': 'GROUP'}})

        await self.middleware.call('ctdb.accounts.general.batch_ops', batch_ops)

        await self.middleware.call('etc.generate', 'user')
        pdb_job = await self.middleware.call('smb.synchronize_passdb')
        await pdb_job.wait()

        await self.middleware.call('ctdb.accounts.general.remote_op_send', {'action': 'RELOAD'})


class CtdbGroupService(CRUDService):

    class Config:
        namespace = 'cluster.accounts.group'
        cli_namespace = 'cluster.accounts.group'

    entry_keys = ['gid', 'group', 'internal', 'users']

    @filterable
    async def query(self, filters, options):
        entries = await self.middleware.call(
            'ctdb.accounts.general.entries',
            [['entry_type', '=', 'GROUP']],
            {'select': self.entry_keys.copy()}
        )
        return filter_list(entries, filters, options)

    @private
    async def create_internal(self, data):
        # NOTE: this method is used by cluster.accounts.user.create to generate
        # the primary group for the user, as well as the cluster.accounts.group.create
        # method. This means that any changes to this method should be confirmed to
        # not cause regression in user creation.
        existing_groups = await self.query([], {'order_by': ['-gid']})

        if filter_list(existing_groups, [['group_name', '=', data['group']]]):
            raise CallError(
                f'{data["group"]}: group already exists. Clustered group names are case-insensitive and '
                'must be unique.'
            )

        data['gid'] = existing_groups[0]['gid'] + 1 if existing_groups else ID_LWM
        return data

    @private
    async def common_validate(self, schema, old, new, verrors):
        current_groups = await self.query()
        to_check = None

        if new['users']:
            # make sure any uids specified exist as clustered users
            # we don't allow local users or made-up numbers here
            existing_uids = [x['uid'] for x in await self.middleware.call('cluster.accounts.user.query')]
            if (unmapped := set(new['users']) - set(existing_uids)):
                verrors.add(
                    f'{schema}.users',
                    f'The following users do not exist as clusterd users: {", ".join(unmapped)}'
                )

        if old is not None:
            if new.get('group') and old['group'] != new['group']:
                to_check = new['group']

        else:
            to_check = new['group']

        # Two things to check here
        # 1) group name is new and already exists as clustered user
        # 2) group name is new and is in-use on one or more other nodes
        # test (2) is somewhat slow and so we skip it if we've already failed (1)
        if to_check and (matched_groups := filter_list(current_groups, [['group', '=', to_check]])):
            verrors.add(
                f'{schema}.group',
                f'This group name is already in use by group ID [{matched_groups[0]["gid"]}]'
            )
        elif to_check:
            try:
                await self.middleware.call('ctdb.accounts.general.remote_op_send', {
                    'action': 'VALIDATE',
                    'entries': [{'id_type': 'GROUP', 'name': to_check}]
                })
            except ValidationError as e:
                #  sample url: http://cl3.nanny.goat:6000/_clusterevents
                url, msg = e.errmsg.split('|', 1)
                hostname = url.rsplit(':', 1)[0].split('http://')[1]
                verrors.add(f'{schema}.username', f'{msg.strip()} on peer {hostname}')
            except Exception:
                self.logger.error('%s: validation of group name failed.', to_check, exc_info=True)
                verrors.add(
                    f'{schema}.group',
                    f'{to_check}: group name already in use on remote node.'
                )

    @accepts(Dict(
        'ctdb_account_group',
        Str('group', required=True),
        List('users', items=[Int('uid')]),
        register=True
    ))
    async def create(self, data):
        """
        WARNING: clustering APIs are not intended for 3rd-party consumption and may result
        in a misconfigured SCALE cluster, production outage, or data loss.

        Create a new clustered group. These are used for SMB access on truenas cluster

        `group` - Group name. Case-insensitive

        `users` - List of clustered users (user IDs) who are a member of this group

        NOTE: clustered groups will not be added to the SMB group mapping database as this
        only provides a minor cosmetic benefit and has no impact on SMB share access via
        the groups.
        """
        data['group'] = data['group'].lower()

        verrors = ValidationErrors()
        await self.common_validate('cluster_accounts_group_create', None, data, verrors)
        pw_checkname(verrors, 'cluster_accounts_group_create.group', data['group'])
        verrors.check()
        data = await self.create_internal(data | {'internal': False})
        await self.middleware.call(
            'ctdb.accounts.general.store', f'GROUP{data["gid"]}', data | {'entry_type': 'GROUP'}
        )
        await self.middleware.call('etc.generate', 'user')

        await self.middleware.call('ctdb.accounts.general.remote_op_send', {'action': 'RELOAD'})
        return data

    @accepts(
        Int('gid', required=True),
        Patch(
            'ctdb_account_group',
            'ctdb_account_group_update',
            ('attr', {'update': True}),
        )
    )
    async def update(self, gid, new):
        """
        WARNING: clustering APIs are not intended for 3rd-party consumption and may result
        in a misconfigured SCALE cluster, production outage, or data loss.

        Update a clustered group by `gid`.
        """
        old = await self.middleware.call('ctdb.accounts.general.fetch', f'GROUP{gid}')

        verrors = ValidationErrors()
        if old['internal']:
            verrors.add(
                'cluster_accounts_group_update',
                f'{gid}: changes to primary groups of users are not permitted.'
            )

        if new.get('group'):
            pw_checkname(verrors, 'cluster_accounts_group_update.group', new['group'])

        await self.common_validate('cluster_accounts_group_update', old, new, verrors)
        verrors.check()
        data = old | new
        await self.middleware.call('ctdb.accounts.general.store', f'GROUP{data["gid"]}', data)

        await self.middleware.call('etc.generate', 'user')

        await self.middleware.call('ctdb.accounts.general.remote_op_send', {'action': 'RELOAD'})
        data.pop('entry_type')
        return data

    @accepts(Int('gid', required=True))
    async def delete(self, gid):
        """
        WARNING: clustering APIs are not intended for 3rd-party consumption and may result
        in a misconfigured SCALE cluster, production outage, or data loss.

        Delete a clustered group by `gid`.
        """
        old = await self.middleware.call('ctdb.accounts.general.fetch', f'GROUP{gid}')

        # `internal` means that it's the primary group of a user
        # check whether the user exists prior to deletion.
        if old['internal']:
            try:
                user = await self.middleware.call('ctdb.accounts.general.fetch', f'USER{old["users"][0]}')
                raise CallError(
                    f'{gid}: gid is primary group for {user["username"]}. User must be removed before group'
                )
            except KeyError:
                # This is a stale primary group and so safe to be deleted.
                pass

        await self.middleware.call('ctdb.accounts.general.remove', f'GROUP{gid}')
        await self.middleware.call('etc.generate', 'user')

        await self.middleware.call('ctdb.accounts.general.remote_op_send', {'action': 'RELOAD'})
