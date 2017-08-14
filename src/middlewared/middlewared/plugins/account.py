from middlewared.schema import accepts, Bool, Dict, Int, Str
from middlewared.service import CallError, CRUDService, filterable, private
from middlewared.utils import run

import errno
import os


class UserService(CRUDService):

    @filterable
    async def query(self, filters=None, options=None):
        options = options or {}
        options['extend'] = 'user.user_extend'
        options['prefix'] = 'bsdusr_'
        return await self.middleware.call('datastore.query', 'account.bsdusers', filters, options)

    @private
    async def user_extend(self, user):
        # Get authorized keys
        keysfile = f'{user["home"]}/.ssh/authorized_keys'
        user['sshpubkey'] = None
        if os.path.exists(keysfile):
            try:
                with open(keysfile, 'r') as f:
                    user['sshpubkey'] = f.read()
            except Exception:
                pass
        return user

    @accepts(Dict(
        'user_create',
        Int('uid', required=True),
        Str('username', required=True),
        Int('group'),
        Bool('group_create', default=False),
        Str('home', default='/nonexistent'),
        Str('shell', default='/bin/csh'),
        Str('full_name'),
        Str('email'),
        Str('mode'),
        Bool('password_disabled', default=False),
        Bool('locked', default=False),
        Bool('microsoft_account', default=False),
        Dict('attributes', additional_attrs=True),
        register=True,
    ))
    async def do_create(self, data):
        users = await self.middleware.call('datastore.query', 'account.bsdusers', [('username', '=', data['username'])], {'prefix': 'bsdusr_'})
        if users:
            raise CallError(f'A user with the username "{data["username"]}" already exists', errno.EEXIST)

        if (
            not data.get('group') and not data.get('group_create')
        ) or (
            data.get('group') is not None and data.get('group_create')
        ):
            raise CallError(f'You need to either provide a group or group_create', errno.EINVAL)

        if 'group_create' in data:
            create = data.pop('group_create')
            if create:
                raise CallError('Creating a group not yet supported')

        pk = await self.middleware.call('datastore.insert', 'account.bsdusers', data, {'prefix': 'bsdusr_'})

        await self.middleware.call('service.reload', 'user')
        return pk

    async def do_update(self, id, data):

        user = await self.middleware.call('datastore.query', 'account.bsdusers', [('id', '=', id)], {'prefix': 'bsdusr_'})
        if not user:
            raise CallError(f'User {id} does not exist', errno.ENOENT)
        user = user[0]

        if 'sshpubkey' in data:
            keysfile = f'{user["home"]}/.ssh/authorized_keys'
            pubkey = data.pop('sshpubkey')
            if pubkey is None:
                if os.path.exists(keysfile):
                    try:
                        os.unlink(keysfile)
                    except OSError:
                        pass
            else:
                oldpubkey = ''
                try:
                    with open(keysfile, 'r') as f:
                        oldpubkey = f.read()
                except Exception:
                    pass
                pubkey = pubkey.strip() + '\n'
                if pubkey != oldpubkey:
                    sshpath = f'{user["home"]}/.ssh'
                    saved_umask = os.umask(0o77)
                    if not os.path.isdir(sshpath):
                        os.makedirs(sshpath)
                    if not os.path.isdir(sshpath):
                        raise CallError(f'{sshpath} is not a directory')
                    if pubkey == '' and os.path.exists(keysfile):
                        os.unlink(keysfile)
                    else:
                        with open(keysfile, 'w') as f:
                            f.write(pubkey)
                        await run('chown', '-R', f'{user["username"]}:{user["group"]["bsdgrp_group"]}', sshpath, check=False)
                    os.umask(saved_umask)

        await self.middleware.call('service.reload', 'user')


class GroupService(CRUDService):

    @filterable
    async def query(self, filters=None, options=None):
        options = options or {}
        options['prefix'] = 'bsdgrp_'
        return await self.middleware.call('datastore.query', 'account.bsdgroups', filters, options)
