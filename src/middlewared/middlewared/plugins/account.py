from middlewared.schema import accepts, Bool, Dict, Int, List, Str
from middlewared.service import CallError, CRUDService, filterable, private
from middlewared.utils import run, Popen

import asyncio
import binascii
import crypt
import errno
import hashlib
import os
import random
import shutil
import string
import subprocess
import time


def pw_checkname(name):
    """
    Makes sure the provided `name` is a valid unix name.
    """
    if name.startswith('-'):
        raise CallError('Your name cannot start with "-"')
    if name.find('$') not in (-1, len(name) - 1):
        raise CallError(
            'The character $ is only allowed as the final character'
        )
    invalid_chars = ' ,\t:+&#%\^()!@~\*?<>=|\\/"'
    invalids = []
    for char in name:
        # invalid_chars nor 8-bit characters are allowed
        if (
            char in invalid_chars and char not in invalids
        ) or ord(char) & 0x80:
            invalids.append(char)
    if invalids:
        raise CallError(
            f'Your name contains invalid characters ({", ".join(invalids)})'
        )


def crypted_password(cleartext):
    """
    Generates an unix hash from `cleartext`.
    """
    return crypt.crypt(cleartext, '$6$' + ''.join([
        random.choice(string.ascii_letters + string.digits) for _ in range(16)]
    ))


def nt_password(cleartext):
    nthash = hashlib.new('md4', cleartext.encode('utf-16le')).digest()
    return binascii.hexlify(nthash).decode().upper()


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
        Str('home_mode', default='755'),
        Str('shell', default='/bin/csh'),
        Str('full_name', required=True),
        Str('email'),
        Str('password'),
        Bool('password_disabled', default=False),
        Bool('locked', default=False),
        Bool('microsoft_account', default=False),
        Bool('sudo', default=False),
        Str('sshpubkey'),
        List('groups'),
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

        pw_checkname(data['username'])

        password = data.get('password')
        if password and '?' in password:
            # See bug #4098
            raise CallError(
                'Passwords containing a question mark (?) are currently not '
                'allowed due to problems with SMB.',
                errno.EINVAL
            )

        if not password and not data.get('password_disabled'):
            raise CallError('Password is required')
        elif data.get('password_disabled') and password:
            raise CallError('Password disabled, leave password blank')

        if data.get('sshpubkey') and not data['home'].startswith('/mnt'):
            raise CallError('Home directory is not writable, leave this blank"')

        if ':' in data['home']:
            raise CallError('Home directory cannot contain colons')

        create = data.pop('group_create')
        if create:
            groups = await self.middleware.call('group.query', [('group', '=', data['username'])])
            if groups:
                group = groups[0]
            else:
                raise CallError('Creating a group not yet supported')
        else:
            group = await self.middleware.call('group.query', [('id', '=', data['group'])])
            if not group:
                raise CallError(f'Group {data["group"]} not found')
            group = group[0]

        # Is this a new directory or not? Let's not nuke existing directories,
        # e.g. /, /root, /mnt/tank/my-dataset, etc ;).
        new_homedir = False
        home_mode = data.pop('home_mode')
        if data['home'] != '/nonexistent':
            try:
                os.makedirs(data['home'], mode=int(home_mode, 8))
                if os.stat(data['home']).st_dev == os.stat('/mnt').st_dev:
                    raise CallError(
                        f'Path for the home directory (data["home"]) '
                        'must be under a volume or dataset'
                    )
            except OSError as oe:
                if oe.errno == errno.EEXIST:
                    if not os.path.isdir(data['home']):
                        raise CallError(
                            'Path for home directory already '
                            'exists and is not a directory'
                        )
                else:
                    raise CallError(
                        'Failed to create the home directory '
                        f'({data["home"]}) for user: {oe}'
                    )
            else:
                new_homedir = True

        pk = None  # Make sure pk exists to rollback in case of an error
        try:
            password = data.pop('password', None)
            if password:
                data['unixhash'] = crypted_password(password)
                # See http://samba.org.ru/samba/docs/man/manpages/smbpasswd.5.html
                data['smbhash'] = f'{data["username"]}:{data["uid"]}:{"X" * 32}:{nt_password(password)}:[U          ]:LCT-{int(time.time()):X}:'
            else:
                data['unixhash'] = '*'
                data['smbhash'] = '*'

            await self.__update_sshpubkey(data, group['group'])

            groups = data.pop('groups') or []

            pk = await self.middleware.call('datastore.insert', 'account.bsdusers', data, {'prefix': 'bsdusr_'})

            for _id in groups:
                group = await self.middleware.call('datastore.query', 'account.bsdgroups', [('id', '=', _id)], {'prefix': 'bsdgrp_'})
                if not group:
                    raise CallError(f'Group {_id} not found', errno.ENOENT)
                await self.middleware.call(
                    'datastore.insert',
                    'account.bsdgroupmembership',
                    {'group': _id, 'user': pk},
                    {'prefix': 'bsdgrpmember_'}
                )

        except Exception:
            if pk is not None:
                await self.middleware.call('datastore.delete', 'account.bsdusers', pk)
            if new_homedir:
                # Be as atomic as possible when creating the user if
                # commands failed to execute cleanly.
                shutil.rmtree(data['home'])
            raise

        await self.middleware.call('service.reload', 'user')

        if password:
            proc = await Popen(['smbpasswd', '-D', '0', '-s', '-a', data['username']], stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
            await proc.communicate(input=f'{password}\n{password}\n'.encode())
        return pk

    async def do_update(self, id, data):

        user = await self.middleware.call('datastore.query', 'account.bsdusers', [('id', '=', id)], {'prefix': 'bsdusr_'})
        if not user:
            raise CallError(f'User {id} does not exist', errno.ENOENT)
        user = user[0]

        if 'group' in data:
            group = await self.middleware.call('datastore.query', 'account.bsdgroups', [('id', '=', data['group'])], {'prefix': 'bsdgrp_'})
            if not group:
                raise CallError(f'Group {data["group"]} not found', errno.ENOENT)
            group = group[0]
        else:
            group = user['group']
            user['group'] = group['id']

        # Copy the home directory if it changed
        if 'home' in data and data['home'] not in (user['home'], '/nonexistent'):
            home_copy = True
            home_old = user['home']
        else:
            home_copy = False

        user.update(data)

        await self.__update_sshpubkey(user, group['group'])

        home_mode = user.pop('home_mode', None)
        if home_mode is not None:
            if not user['builtin'] and os.path.exists(user['home']):
                try:
                    os.chmod(user['home'], int(home_mode, 8))
                except OSError:
                    self.logger.warn('Failed to set homedir mode', exc_info=True)

        if home_copy:
            def do_home_copy():
                subprocess.run(f"su - {user['username']} -c '/bin/cp -a {home_old}/* {user['home']}/'")
            asyncio.ensure_future(self.middleware.threaded(do_home_copy))

        await self.middleware.call('service.reload', 'user')



        return id

    async def __update_sshpubkey(self, user, group):
        if 'sshpubkey' in user:
            keysfile = f'{user["home"]}/.ssh/authorized_keys'
            pubkey = user.pop('sshpubkey')
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
                        await run('chown', '-R', f'{user["username"]}:{group}', sshpath, check=False)
                    os.umask(saved_umask)


class GroupService(CRUDService):

    @filterable
    async def query(self, filters=None, options=None):
        options = options or {}
        options['prefix'] = 'bsdgrp_'
        return await self.middleware.call('datastore.query', 'account.bsdgroups', filters, options)
