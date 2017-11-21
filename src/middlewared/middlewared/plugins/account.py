from middlewared.schema import accepts, Bool, Dict, Int, List, Patch, Str
from middlewared.service import (
    CallError, CRUDService, ValidationErrors, private
)
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

SKEL_PATH = '/usr/share/skel/'


def pw_checkname(verrors, attribute, name):
    """
    Makes sure the provided `name` is a valid unix name.
    """
    if name.startswith('-'):
        verrors.add(attribute, 'Your name cannot start with "-"')
    if name.find('$') not in (-1, len(name) - 1):
        verrors.add(
            attribute,
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
        verrors.add(
            attribute,
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

    class Config:
        datastore = 'account.bsdusers'
        datastore_extend = 'user.user_extend'
        datastore_prefix = 'bsdusr_'

    @private
    async def user_extend(self, user):

        # Get group membership
        user['groups'] = [gm['group']['id'] for gm in await self.middleware.call('datastore.query', 'account.bsdgroupmembership', [('user', '=', user['id'])], {'prefix': 'bsdgrpmember_'})]

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
        Int('uid'),
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

        verrors = ValidationErrors()

        if (
            not data.get('group') and not data.get('group_create')
        ) or (
            data.get('group') is not None and data.get('group_create')
        ):
            verrors.add('group', f'You need to either provide a group or group_create', errno.EINVAL)

        await self.__common_validation(verrors, data)

        if data.get('sshpubkey') and not data['home'].startswith('/mnt'):
            verrors.add('sshpubkey', 'Home directory is not writable, leave this blank"')

        if verrors:
            raise verrors

        groups = data.pop('groups') or []
        create = data.pop('group_create')

        if create:
            group = await self.middleware.call('group.query', [('group', '=', data['username'])])
            if group:
                group = group[0]
            else:
                group = await self.middleware.call('group.create', {'name': data['username']})
                group = (await self.middleware.call('group.query', [('id', '=', group)]))[0]
            data['group'] = group['id']
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
            except FileExistsError:
                if not os.path.isdir(data['home']):
                    raise CallError(
                        'Path for home directory already '
                        'exists and is not a directory',
                        errno.EEXIST
                    )
            except OSError as oe:
                raise CallError(
                    'Failed to create the home directory '
                    f'({data["home"]}) for user: {oe}'
                )
            else:
                new_homedir = True
            if os.stat(data['home']).st_dev == os.stat('/mnt').st_dev:
                raise CallError(
                    f'Path for the home directory (data["home"]) '
                    'must be under a volume or dataset'
                )

        if not data.get('uid'):
            data['uid'] = await self.get_next_uid()

        pk = None  # Make sure pk exists to rollback in case of an error
        try:

            password = await self.__set_password(data)

            await self.__update_sshpubkey(data, group['group'])

            pk = await self.middleware.call('datastore.insert', 'account.bsdusers', data, {'prefix': 'bsdusr_'})

            await self.__set_groups(pk, groups)

        except Exception:
            if pk is not None:
                await self.middleware.call('datastore.delete', 'account.bsdusers', pk)
            if new_homedir:
                # Be as atomic as possible when creating the user if
                # commands failed to execute cleanly.
                shutil.rmtree(data['home'])
            raise

        await self.middleware.call('service.reload', 'user')

        await self.__set_smbpasswd(data['username'], password)

        if os.path.exists(data['home']):
            for f in os.listdir(SKEL_PATH):
                if f.startswith('dot'):
                    dest_file = os.path.join(data['home'], f[3:])
                else:
                    dest_file = os.path.join(data['home'], f)
                if not os.path.exists(dest_file):
                    shutil.copyfile(os.path.join(SKEL_PATH, f), dest_file)
                    os.chown(dest_file, data['uid'], group['gid'])

        return pk

    @accepts(
        Int('id'),
        Patch(
            'user_create',
            'user_update',
            ('attr', {'update': True}),
            ('rm', {'name': 'group_create'}),
        ),
    )
    async def do_update(self, pk, data):

        user = await self._get_instance(pk)

        verrors = ValidationErrors()

        if 'group' in data:
            group = await self.middleware.call('datastore.query', 'account.bsdgroups', [('id', '=', data['group'])])
            if not group:
                verrors.add('group', f'Group {data["group"]} not found', errno.ENOENT)
            group = group[0]
        else:
            group = user['group']
            user['group'] = group['id']

        await self.__common_validation(verrors, data, pk=pk)

        home = data.get('home') or user['home']
        # root user (uid 0) is an exception to the rule
        if data.get('sshpubkey') and not home.startswith('/mnt') and user['uid'] != 0:
            verrors.add('sshpubkey', 'Home directory is not writable, leave this blank"')

        # Do not allow attributes to be changed for builtin user
        if user['builtin']:
            for i in ('group', 'home', 'home_mode', 'uid', 'username'):
                if i in data:
                    verrors.add(i, 'This attribute cannot be changed')

        if verrors:
            raise verrors

        # Copy the home directory if it changed
        if (
            'home' in data and
            data['home'] not in (user['home'], '/nonexistent') and
            not data["home"].startswith(f'{user["home"]}/')
        ):
            home_copy = True
            home_old = user['home']
        else:
            home_copy = False

        user.update(data)

        password = await self.__set_password(user)

        await self.__update_sshpubkey(user, group['bsdgrp_group'])

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
            asyncio.ensure_future(self.middleware.run_in_thread(do_home_copy))

        if 'groups' in user:
            groups = user.pop('groups')
            await self.__set_groups(pk, groups)

        await self.middleware.call('datastore.update', 'account.bsdusers', pk, user, {'prefix': 'bsdusr_'})

        await self.middleware.call('service.reload', 'user')

        await self.__set_smbpasswd(user['username'], password)

        return pk

    @accepts(Int('id'), Dict('options', Bool('delete_group', default=True)))
    async def do_delete(self, pk, options=None):

        user = await self._get_instance(pk)

        if user['builtin']:
            raise CallError('Cannot delete a built-in user', errno.EINVAL)

        if options['delete_group'] and not user['group']['bsdgrp_builtin']:
            count = await self.middleware.call('datastore.query', 'account.bsdgroupmembership', [('group', '=', user['group']['id'])], {'prefix': 'bsdgrpmember_', 'count': True})
            count2 = await self.middleware.call('datastore.query', 'account.bsdusers', [('group', '=', user['group']['id']), ('id', '!=', pk)], {'prefix': 'bsdusr_', 'count': True})
            if count == 0 and count2 == 0:
                try:
                    await self.middleware.call('group.delete', user['group']['id'])
                except Exception:
                    self.logger.warn(f'Failed to delete primary group of {user["username"]}', exc_info=True)

        await run('smbpasswd', '-x', user['username'], check=False)

        if await self.middleware.call('notifier.common', 'system', 'domaincontroller_enabled'):
            await self.middleware.call('notifier.samba4', 'user_delete', user['username'])

        # TODO: add a hook in CIFS service
        cifs = await self.middleware.call('datastore.query', 'services.cifs', [], {'prefix': 'cifs_srv_'})
        if cifs:
            cifs = cifs[0]
            if cifs['guest'] == user['username']:
                await self.middleware.call('datastore.update', 'services.cifs', cifs['id'], {'guest': 'nobody'}, {'prefix': 'cifs_srv_'})

        await self.middleware.call('datastore.delete', 'account.bsdusers', pk)
        await self.middleware.call('service.reload', 'user')

        return pk

    async def get_next_uid(self):
        """
        Get the next available/free uid.
        """
        last_uid = 999
        for i in await self.middleware.call('datastore.query', 'account.bsdusers', [('builtin', '=', False)], {'order_by': ['uid'], 'prefix': 'bsdusr_'}):
            # If the difference between the last uid and the current one is
            # bigger than 1, it means we have a gap and can use it.
            if i['uid'] - last_uid > 1:
                return last_uid + 1
            last_uid = i['uid']
        return last_uid + 1

    async def __common_validation(self, verrors, data, pk=None):

        exclude_filter = [('id', '!=', pk)] if pk else []

        if 'username' in data:
            pw_checkname(verrors, 'username', data['username'])

            if await self.middleware.call('datastore.query', 'account.bsdusers', [('username', '=', data['username'])] + exclude_filter, {'prefix': 'bsdusr_'}):
                verrors.add('username', f'A user with the username "{data["username"]}" already exists', errno.EEXIST)

        password = data.get('password')
        if password and '?' in password:
            # See bug #4098
            verrors.add(
                'password',
                'Passwords containing a question mark (?) are currently not '
                'allowed due to problems with SMB.',
                errno.EINVAL
            )
        elif not pk and not password and not data.get('password_disabled'):
            verrors.add('password', 'Password is required')
        elif data.get('password_disabled') and password:
            verrors.add('password_disabled', 'Password disabled, leave password blank')

        if 'home' in data:
            if ':' in data['home']:
                verrors.add('home', 'Home directory cannot contain colons')
            if not data['home'].startswith('/mnt/') and data['home'] != '/nonexistent':
                verrors.add('home', 'Home directory has to start with /mnt/ or be /nonexistent')

        if 'groups' in data:
            groups = data.get('groups') or []
            if groups and len(groups) > 64:
                verrors.add('groups', 'A user cannot belong to more than 64 auxiliary groups')

        if 'full_name' in data and ':' in data['full_name']:
            verrors.add('full_name', '":" character is not allowed in Full Name')

    async def __set_password(self, data):
        if 'password' not in data:
            return
        password = data.pop('password')
        if password:
            data['unixhash'] = crypted_password(password)
            # See http://samba.org.ru/samba/docs/man/manpages/smbpasswd.5.html
            data['smbhash'] = f'{data["username"]}:{data["uid"]}:{"X" * 32}:{nt_password(password)}:[U          ]:LCT-{int(time.time()):X}:'
        else:
            data['unixhash'] = '*'
            data['smbhash'] = '*'
        return password

    async def __set_smbpasswd(self, username, password):
        """
        Currently the way we set samba passwords is using smbpasswd
        and that can only happen after the user exists in master.passwd.
        That is the reason we have two methods/steps to set password.
        """
        if not password:
            return
        proc = await Popen(['smbpasswd', '-D', '0', '-s', '-a', username], stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
        await proc.communicate(input=f'{password}\n{password}\n'.encode())

    async def __set_groups(self, pk, groups):

        groups = set(groups)
        existing_ids = set()
        for gm in await self.middleware.call('datastore.query', 'account.bsdgroupmembership', [('user', '=', pk)], {'prefix': 'bsdgrpmember_'}):
            if gm['id'] not in groups:
                await self.middleware.call('datastore.delete', 'account.bsdgroupmembership', gm['id'])
            else:
                existing_ids.add(gm['id'])

        for _id in groups - existing_ids:
            group = await self.middleware.call('datastore.query', 'account.bsdgroups', [('id', '=', _id)], {'prefix': 'bsdgrp_'})
            if not group:
                raise CallError(f'Group {_id} not found', errno.ENOENT)
            await self.middleware.call(
                'datastore.insert',
                'account.bsdgroupmembership',
                {'group': _id, 'user': pk},
                {'prefix': 'bsdgrpmember_'}
            )

    async def __update_sshpubkey(self, user, group):
        if 'sshpubkey' not in user:
            return
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
                if not os.path.isdir(sshpath):
                    os.makedirs(sshpath)
                    os.chmod(sshpath, 0o700)
                if not os.path.isdir(sshpath):
                    raise CallError(f'{sshpath} is not a directory')
                if pubkey == '' and os.path.exists(keysfile):
                    os.unlink(keysfile)
                else:
                    with open(keysfile, 'w') as f:
                        f.write(pubkey)
                    os.chmod(keysfile, 0o700)
                    await run('chown', '-R', f'{user["username"]}:{group}', sshpath, check=False)


class GroupService(CRUDService):

    class Config:
        datastore = 'account.bsdgroups'
        datastore_prefix = 'bsdgrp_'

    @accepts(Dict(
        'group_create',
        Int('gid'),
        Str('name', required=True),
        Bool('sudo', default=False),
        Bool('allow_duplicate_gid', default=False),
        register=True,
    ))
    async def do_create(self, data):

        verrors = ValidationErrors()
        await self.__common_validation(verrors, data)
        if verrors:
            raise verrors

        if not data.get('gid'):
            data['gid'] = await self.get_next_gid()

        group = data.copy()
        group['group'] = group.pop('name')
        pk = await self.middleware.call('datastore.insert', 'account.bsdgroups', group, {'prefix': 'bsdgrp_'})

        await self.middleware.call('notifier.groupmap_add', data['name'], data['name'])

        await self.middleware.call('service.reload', 'user')

        return pk

    @accepts(
        Int('id'),
        Patch(
            'group_create',
            'group_update',
            ('attr', {'update': True}),
        ),
    )
    async def do_update(self, pk, data):

        group = await self._get_instance(pk)

        verrors = ValidationErrors()
        await self.__common_validation(verrors, data, pk=pk)
        if verrors:
            raise verrors

        group.update(data)
        delete_groupmap = False
        if 'name' in data and data['name'] != group['group']:
            delete_groupmap = group['group']
            group['group'] = group.pop('name')

        await self.middleware.call('datastore.update', 'account.bsdgroups', pk, group, {'prefix': 'bsdgrp_'})

        if delete_groupmap:
            await self.middleware.call('notifier.groupmap_delete', delete_groupmap)

        await self.middleware.call('notifier.groupmap_add', group['group'], group['group'])

        await self.middleware.call('service.reload', 'user')

        return pk

    @accepts(Int('id'), Dict('options', Bool('delete_users', default=False)))
    async def do_delete(self, pk, options=None):

        group = await self._get_instance(pk)

        if group['builtin']:
            raise CallError('Builtin group cannot be deleted', errno.EACCES)

        if options['delete_users']:
            for i in await self.middleware.call('datastore.query', 'account.bsdusers', [('group', '=', group['id'])], {'prefix': 'bsdusr_'}):
                await self.middleware.call('datastore.delete', 'account.bsdusers', i['id'])

        if await self.middleware.call('notifier.common', 'system', 'domaincontroller_enabled'):
            await self.middleware.call('notifier.samba4', 'group_delete', group['group'])

        await self.middleware.call('datastore.delete', 'account.bsdgroups', pk)

        await self.middleware.call('service.reload', 'user')

        return pk

    async def get_next_gid(self):
        """
        Get the next available/free gid.
        """
        last_gid = 999
        for i in await self.middleware.call('datastore.query', 'account.bsdgroups', [('builtin', '=', False)], {'order_by': ['gid'], 'prefix': 'bsdgrp_'}):
            # If the difference between the last gid and the current one is
            # bigger than 1, it means we have a gap and can use it.
            if i['gid'] - last_gid > 1:
                return last_gid + 1
            last_gid = i['gid']
        return last_gid + 1

    async def __common_validation(self, verrors, data, pk=None):

        exclude_filter = [('id', '!=', pk)] if pk else []

        if 'name' in data:
            existing = await self.middleware.call('datastore.query', 'account.bsdgroups', [('group', '=', data['name'])] + exclude_filter, {'prefix': 'bsdgrp_'})
            if existing:
                verrors.add('name', f'Group with name "{data["name"]}" already exists', errno.EEXIST)

            pw_checkname(verrors, 'name', data['name'])

        allow_duplicate_gid = data.pop('allow_duplicate_gid', False)
        if data.get('gid') and not allow_duplicate_gid:
            existing = await self.middleware.call('datastore.query', 'account.bsdgroups', [('gid', '=', data['gid'])] + exclude_filter, {'prefix': 'bsdgrp_'})
            if existing:
                verrors.add('gid', f'Group ID "{data["gid"]}" already exists', errno.EEXIST)
