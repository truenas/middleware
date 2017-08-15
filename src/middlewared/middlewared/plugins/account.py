from middlewared.schema import accepts, Bool, Dict, Int, Str
from middlewared.service import CallError, CRUDService, filterable, private
from middlewared.utils import run, Popen

import crypt
import errno
import os
import random
import shutil
import string
import subprocess


def crypted_password(cleartext):
    return crypt.crypt(cleartext, '$6$' + ''.join([
        random.choice(string.ascii_letters + string.digits) for _ in range(16)]
    ))


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
        Str('home_mode'),
        Str('shell', default='/bin/csh'),
        Str('full_name', required=True),
        Str('email'),
        Str('password'),
        Bool('password_disabled', default=False),
        Bool('locked', default=False),
        Bool('microsoft_account', default=False),
        Str('sshpubkey'),
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

        create = data.pop('group_create')
        if create:
            raise CallError('Creating a group not yet supported')
        else:
            group = await self.middleware.call('group.query', [('id', '=', data['group'])])

        # Is this a new directory or not? Let's not nuke existing directories,
        # e.g. /, /root, /mnt/tank/my-dataset, etc ;).
        new_homedir = False
        if data['home'] != '/nonexistent':
            try:
                os.makedirs(data['home'], mode=data['home_mode'])
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
        try:
            password = data.pop('password', None)
            if password:
                data['unixhash'] = crypted_password(password)
            else:
                data['unixhash'] = '*'

            pk = await self.middleware.call('datastore.insert', 'account.bsdusers', data, {'prefix': 'bsdusr_'})
        except Exception:
            if new_homedir:
                # Be as atomic as possible when creating the user if
                # commands failed to execute cleanly.
                shutil.rmtree(data['home'])
            raise

        await self.middleware.call('service.reload', 'user')

        if password:
            proc = await Popen(['smbpasswd', '-D', '0', '-s', '-a', data['username']], stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
            await proc.communicate(input=f'{password}\n{password}\n'.encode())
            proc = await Popen(['pdbedit', '-d', '0', '-w', data['username']], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            smbhash = (await proc.communicate())[0].decode().strip()
            await self.middleware.call('datastore.update', 'account.bsdusers', pk, {'bsdusr_smbhash': smbhash})
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
