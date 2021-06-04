from middlewared.schema import accepts, Any, Bool, Dict, Int, List, Patch, returns, Str
from middlewared.service import (
    CallError, CRUDService, ValidationErrors, item_method, no_auth_required, pass_app, private, filterable, job
)
import middlewared.sqlalchemy as sa
from middlewared.utils import run, filter_list
from middlewared.utils.osc import IS_FREEBSD
from middlewared.validators import Email
from middlewared.plugins.smb import SMBBuiltin

import binascii
import crypt
import errno
import glob
import hashlib
import os
import random
import shlex
import shutil
import string
import stat
import time
from pathlib import Path

SKEL_PATH = '/etc/skel/'


def pw_checkname(verrors, attribute, name):
    """
    Makes sure the provided `name` is a valid unix name.
    """
    if name.startswith('-'):
        verrors.add(
            attribute,
            'Name must begin with an alphanumeric character and not a '
            '"-".'
        )
    if name.find('$') not in (-1, len(name) - 1):
        verrors.add(
            attribute,
            'The character $ is only allowed as the final character.'
        )
    invalid_chars = ' ,\t:+&#%^()!@~*?<>=|\\/"'
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
            f'name contains invalid characters: {", ".join(invalids)}'
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


def validate_sudo_commands(commands):
    verrors = ValidationErrors()
    for i, command in enumerate(commands):
        try:
            executable = shlex.split(command)[0]

            if not executable.startswith('/'):
                raise ValueError('Executable must be an absolute path')

            if os.path.normpath(executable).rstrip('/') != executable.rstrip('/'):
                raise ValueError('Executable path must be normalized')

            paths = glob.glob(executable)
            if not paths:
                raise ValueError(f'No paths matching {executable!r} exist')

            if not executable.endswith('/'):
                for item in paths:
                    if os.path.isfile(item) and os.access(item, os.X_OK):
                        break
                else:
                    raise ValueError(f'None of the paths matching {executable!r} is executable')
        except ValueError as e:
            verrors.add(f'{i}', str(e))

    return verrors


class UserModel(sa.Model):
    __tablename__ = 'account_bsdusers'

    id = sa.Column(sa.Integer(), primary_key=True)
    bsdusr_uid = sa.Column(sa.Integer())
    bsdusr_username = sa.Column(sa.String(16), default='User &', unique=True)
    bsdusr_unixhash = sa.Column(sa.String(128), default='*')
    bsdusr_smbhash = sa.Column(sa.EncryptedText(), default='*')
    bsdusr_home = sa.Column(sa.String(255), default="/nonexistent")
    bsdusr_shell = sa.Column(sa.String(120), default='/bin/csh')
    bsdusr_full_name = sa.Column(sa.String(120))
    bsdusr_builtin = sa.Column(sa.Boolean(), default=False)
    bsdusr_smb = sa.Column(sa.Boolean(), default=True)
    bsdusr_password_disabled = sa.Column(sa.Boolean(), default=False)
    bsdusr_locked = sa.Column(sa.Boolean(), default=False)
    bsdusr_sudo = sa.Column(sa.Boolean(), default=False)
    bsdusr_sudo_nopasswd = sa.Column(sa.Boolean())
    bsdusr_sudo_commands = sa.Column(sa.JSON(type=list))
    bsdusr_microsoft_account = sa.Column(sa.Boolean())
    bsdusr_group_id = sa.Column(sa.ForeignKey('account_bsdgroups.id'), index=True)
    bsdusr_attributes = sa.Column(sa.JSON())
    bsdusr_email = sa.Column(sa.String(254), nullable=True)


class UserService(CRUDService):
    """
    Manage local users
    """

    class Config:
        datastore = 'account.bsdusers'
        datastore_extend = 'user.user_extend'
        datastore_prefix = 'bsdusr_'
        cli_namespace = 'account.user'

    # FIXME: Please see if dscache can potentially alter result(s) format, without ad, it doesn't seem to
    ENTRY = Patch(
        'user_create', 'user_entry',
        ('rm', {'name': 'group'}),
        ('rm', {'name': 'group_create'}),
        ('rm', {'name': 'home_mode'}),
        ('rm', {'name': 'password'}),
        ('add', Dict('group', additional_attrs=True)),
        ('add', Int('id')),
        ('add', Bool('builtin')),
        ('add', Bool('id_type_both')),
        ('add', Bool('local')),
        ('add', Str('unixhash')),
        ('add', Str('smbhash')),
    )

    @private
    async def user_extend(self, user):

        # Normalize email, empty is really null
        if user['email'] == '':
            user['email'] = None

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

    @private
    async def user_compress(self, user):
        if 'local' in user:
            user.pop('local')
        if 'id_type_both' in user:
            user.pop('id_type_both')
        return user

    @filterable
    async def query(self, filters, options):
        """
        Query users with `query-filters` and `query-options`. As a performance optimization, only local users
        will be queried by default.

        Users from directory services such as NIS, LDAP, or Active Directory will be included in query results
        if the option `{'extra': {'search_dscache': True}}` is specified.
        """
        if not filters:
            filters = []

        options = options or {}
        options['extend'] = self._config.datastore_extend
        options['extend_context'] = self._config.datastore_extend_context
        options['prefix'] = self._config.datastore_prefix

        datastore_options = options.copy()
        datastore_options.pop('count', None)
        datastore_options.pop('get', None)
        datastore_options.pop('limit', None)
        datastore_options.pop('offset', None)

        extra = options.get('extra', {})
        dssearch = extra.pop('search_dscache', False)

        if dssearch:
            return await self.middleware.call('dscache.query', 'USERS', filters, options)

        result = await self.middleware.call(
            'datastore.query', self._config.datastore, [], datastore_options
        )
        for entry in result:
            entry.update({'local': True, 'id_type_both': False})
        return await self.middleware.run_in_thread(
            filter_list, result, filters, options
        )

    @accepts(Dict(
        'user_create',
        Int('uid'),
        Str('username', required=True, max_length=16),
        Int('group'),
        Bool('group_create', default=False),
        Str('home', default='/nonexistent'),
        Str('home_mode', default='755'),
        Str('shell', default='/bin/csh' if IS_FREEBSD else '/usr/bin/zsh'),
        Str('full_name', required=True),
        Str('email', validators=[Email()], null=True, default=None),
        Str('password', private=True),
        Bool('password_disabled', default=False),
        Bool('locked', default=False),
        Bool('microsoft_account', default=False),
        Bool('smb', default=True),
        Bool('sudo', default=False),
        Bool('sudo_nopasswd', default=False),
        List('sudo_commands', items=[Str('command', empty=False)]),
        Str('sshpubkey', null=True, max_length=None),
        List('groups'),
        Dict('attributes', additional_attrs=True),
        register=True,
    ))
    @returns(Int('primary_key'))
    async def do_create(self, data):
        """
        Create a new user.

        If `uid` is not provided it is automatically filled with the next one available.

        `group` is required if `group_create` is false.

        `password` is required if `password_disabled` is false.

        Available choices for `shell` can be retrieved with `user.shell_choices`.

        `attributes` is a general-purpose object for storing arbitrary user information.

        `smb` specifies whether the user should be allowed access to SMB shares. User
        will also automatically be added to the `builtin_users` group.
        """
        verrors = ValidationErrors()

        if (
            not data.get('group') and not data.get('group_create')
        ) or (
            data.get('group') is not None and data.get('group_create')
        ):
            verrors.add(
                'user_create.group',
                f'Enter either a group name or create a new group to '
                'continue.',
                errno.EINVAL
            )

        await self.__common_validation(verrors, data, 'user_create')

        if data.get('sshpubkey') and not data['home'].startswith('/mnt'):
            verrors.add(
                'user_create.sshpubkey',
                'The home directory is not writable. Leave this field blank.'
            )

        verrors.check()

        groups = data.pop('groups')
        create = data.pop('group_create')

        if create:
            group = await self.middleware.call('group.query', [('group', '=', data['username'])])
            if group:
                group = group[0]
            else:
                group = await self.middleware.call('group.create_internal', {
                    'name': data['username'],
                    'smb': False,
                    'sudo': False,
                    'sudo_nopasswd': False,
                    'sudo_commands': [],
                    'allow_duplicate_gid': False
                }, False)
                group = (await self.middleware.call('group.query', [('id', '=', group)]))[0]
            data['group'] = group['id']
        else:
            group = await self.middleware.call('group.query', [('id', '=', data['group'])])
            if not group:
                raise CallError(f'Group {data["group"]} not found')
            group = group[0]

        if data['smb']:
            groups.append((await self.middleware.call('group.query',
                                                      [('group', '=', 'builtin_users')],
                                                      {'get': True}))['id'])

        # Is this a new directory or not? Let's not nuke existing directories,
        # e.g. /, /root, /mnt/tank/my-dataset, etc ;).
        new_homedir = False
        home_mode = data.pop('home_mode')
        if data['home'] and data['home'] != '/nonexistent':
            try:
                try:
                    os.makedirs(data['home'], mode=int(home_mode, 8))
                    new_homedir = True
                    await self.middleware.call('filesystem.setperm', {
                        'path': data['home'],
                        'mode': home_mode,
                        'uid': data['uid'],
                        'gid': group['gid'],
                        'options': {'stripacl': True}
                    })
                except FileExistsError:
                    if not os.path.isdir(data['home']):
                        raise CallError(
                            'Path for home directory already '
                            'exists and is not a directory',
                            errno.EEXIST
                        )

                    # If it exists, ensure the user is owner.
                    await self.middleware.call('filesystem.chown', {
                        'path': data['home'],
                        'uid': data['uid'],
                        'gid': group['gid'],
                    })
                except OSError as oe:
                    raise CallError(
                        'Failed to create the home directory '
                        f'({data["home"]}) for user: {oe}'
                    )
            except Exception:
                if new_homedir:
                    shutil.rmtree(data['home'])
                raise

        if not data.get('uid'):
            data['uid'] = await self.get_next_uid()

        pk = None  # Make sure pk exists to rollback in case of an error
        data = await self.user_compress(data)
        try:
            await self.__set_password(data)
            sshpubkey = data.pop('sshpubkey', None)  # datastore does not have sshpubkey

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

        if data['smb']:
            await self.middleware.call('smb.synchronize_passdb')

        if os.path.isdir(SKEL_PATH) and os.path.exists(data['home']):
            for f in os.listdir(SKEL_PATH):
                if f.startswith('dot'):
                    dest_file = os.path.join(data['home'], f[3:])
                else:
                    dest_file = os.path.join(data['home'], f)
                if not os.path.exists(dest_file):
                    shutil.copyfile(os.path.join(SKEL_PATH, f), dest_file)
                    await self.middleware.call('filesystem.chown', {
                        'path': dest_file,
                        'uid': data['uid'],
                        'gid': group['gid'],
                    })

            data['sshpubkey'] = sshpubkey
            try:
                await self.update_sshpubkey(data['home'], data, group['group'])
            except PermissionError as e:
                self.logger.warn('Failed to update authorized keys', exc_info=True)
                raise CallError(f'Failed to update authorized keys: {e}')

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
    @returns(Int('primary_key'))
    async def do_update(self, pk, data):
        """
        Update attributes of an existing user.
        """

        user = await self._get_instance(pk)

        verrors = ValidationErrors()

        if 'group' in data:
            group = await self.middleware.call('datastore.query', 'account.bsdgroups', [
                ('id', '=', data['group'])
            ])
            if not group:
                verrors.add('user_update.group', f'Group {data["group"]} not found', errno.ENOENT)
            group = group[0]
        else:
            group = user['group']
            user['group'] = group['id']

        await self.__common_validation(verrors, data, 'user_update', pk=pk)

        try:
            st = os.stat(user.get("home", "/nonexistent")).st_mode
            old_mode = f'{stat.S_IMODE(st):03o}'
        except FileNotFoundError:
            old_mode = None

        home = data.get('home') or user['home']
        has_home = home != '/nonexistent'
        # root user (uid 0) is an exception to the rule
        if data.get('sshpubkey') and not home.startswith('/mnt') and user['uid'] != 0:
            verrors.add('user_update.sshpubkey', 'Home directory is not writable, leave this blank"')

        # Do not allow attributes to be changed for builtin user
        if user['builtin']:
            for i in ('group', 'home', 'home_mode', 'uid', 'username', 'smb'):
                if i in data and data[i] != user[i]:
                    verrors.add(f'user_update.{i}', 'This attribute cannot be changed')

        if not user['smb'] and data.get('smb') and not data.get('password'):
            # Changing from non-smb user to smb user requires re-entering password.
            verrors.add('user_update.smb',
                        'Password must be changed in order to enable SMB authentication')

        verrors.check()

        must_change_pdb_entry = False
        for k in ('username', 'password', 'locked'):
            new_val = data.get(k)
            old_val = user.get(k)
            if new_val is not None and old_val != new_val:
                if k == 'username':
                    try:
                        await self.middleware.call("smb.remove_passdb_user", old_val)
                    except Exception:
                        self.logger.debug("Failed to remove passdb entry for user [%s]",
                                          old_val, exc_info=True)

                must_change_pdb_entry = True

        if user['smb'] is True and data.get('smb') is False:
            try:
                must_change_pdb_entry = False
                await self.middleware.call("smb.remove_passdb_user", user['username'])
            except Exception:
                self.logger.debug("Failed to remove passdb entry for user [%s]",
                                  user['username'], exc_info=True)

        if user['smb'] is False and data.get('smb') is True:
            must_change_pdb_entry = True

        # Copy the home directory if it changed
        if (
            has_home and
            'home' in data and
            data['home'] != user['home'] and
            not data['home'].startswith(f'{user["home"]}/')
        ):
            home_copy = True
            home_old = user['home']
        else:
            home_copy = False

        # After this point user dict has values from data
        user.update(data)

        if home_copy and not os.path.isdir(user['home']):
            try:
                os.makedirs(user['home'])
                mode_to_set = user.get('home_mode')
                if not mode_to_set:
                    mode_to_set = '700' if old_mode is None else old_mode

                perm_job = await self.middleware.call('filesystem.setperm', {
                    'path': user['home'],
                    'uid': user['uid'],
                    'gid': group['bsdgrp_gid'],
                    'mode': mode_to_set,
                    'options': {'stripacl': True},
                })
                await perm_job.wait()
            except OSError:
                self.logger.warn('Failed to chown homedir', exc_info=True)
            if not os.path.isdir(user['home']):
                raise CallError(f'{user["home"]} is not a directory')

        home_mode = user.pop('home_mode', None)
        if user['builtin']:
            home_mode = None

        try:
            update_sshpubkey_args = [
                home_old if home_copy else user['home'], user, group['bsdgrp_group'],
            ]
            await self.update_sshpubkey(*update_sshpubkey_args)
        except PermissionError as e:
            self.logger.warn('Failed to update authorized keys', exc_info=True)
            raise CallError(f'Failed to update authorized keys: {e}')
        else:
            if user['uid'] == 0:
                if await self.middleware.call('failover.licensed'):
                    try:
                        await self.middleware.call('failover.call_remote', 'user.update_sshpubkey', update_sshpubkey_args)
                    except Exception:
                        self.logger.error('Failed to sync root ssh pubkey to standby node', exc_info=True)

        if home_copy:
            """
            Background copy of user home directoy to new path as the user in question.
            """
            await self.middleware.call('user.do_home_copy', home_old, user['home'], user['username'], home_mode, user['uid'])

        elif has_home and home_mode is not None:
            """
            A non-recursive call to set permissions should return almost immediately.
            """
            perm_job = await self.middleware.call('filesystem.setperm', {
                'path': user['home'],
                'mode': home_mode,
                'options': {'stripacl': True},
            })
            await perm_job.wait()

        user.pop('sshpubkey', None)
        await self.__set_password(user)

        if 'groups' in user:
            groups = user.pop('groups')
            await self.__set_groups(pk, groups)

        user = await self.user_compress(user)
        await self.middleware.call('datastore.update', 'account.bsdusers', pk, user, {'prefix': 'bsdusr_'})

        await self.middleware.call('service.reload', 'user')
        if user['smb'] and must_change_pdb_entry:
            await self.middleware.call('smb.synchronize_passdb')

        return pk

    @accepts(Int('id'), Dict('options', Bool('delete_group', default=True)))
    @returns(Int('primary_key'))
    async def do_delete(self, pk, options):
        """
        Delete user `id`.

        The `delete_group` option deletes the user primary group if it is not being used by
        any other user.
        """

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

        if user['smb']:
            await run('smbpasswd', '-x', user['username'], check=False)

        # TODO: add a hook in CIFS service
        cifs = await self.middleware.call('datastore.query', 'services.cifs', [], {'prefix': 'cifs_srv_'})
        if cifs:
            cifs = cifs[0]
            if cifs['guest'] == user['username']:
                await self.middleware.call('datastore.update', 'services.cifs', cifs['id'], {'guest': 'nobody'}, {'prefix': 'cifs_srv_'})

        await self.middleware.call('datastore.delete', 'account.bsdusers', pk)
        await self.middleware.call('service.reload', 'user')

        return pk

    @accepts(Int('user_id', default=None, null=True))
    @returns(Dict(
        additional_attrs=True,
        example={
            '/usr/bin/sh': 'sh',
            '/usr/bin/zsh': 'zsh',
        }
    ))
    def shell_choices(self, user_id):
        """
        Return the available shell choices to be used in `user.create` and `user.update`.

        If `user_id` is provided, shell choices are filtered to ensure the user can access the shell choices provided.
        """
        user = self.middleware.call_sync('user.get_instance', user_id) if user_id else None

        # on linux /etc/shells has duplicate entries like (/bin/sh, /usr/bin/sh) (/bin/bash, /usr/bin/bash) etc.
        # The entries that point to the same basename are the same binary.
        # The /usr/bin/ path is the "newer" place to put binaries so we'll use those entries.
        path = '/' if IS_FREEBSD else '/usr/bin/'

        with open('/etc/shells', 'r') as f:
            shells = [x.rstrip() for x in f.readlines() if x.startswith(path)]
        return {
            shell: os.path.basename(shell)
            for shell in (shells + ['/usr/sbin/nologin'])
            if 'netcli' not in shell or (user and user['username'] == 'root')
        }

    @accepts(Dict(
        'get_user_obj',
        Str('username', default=None),
        Int('uid', default=None)
    ))
    @returns(Dict(
        'user_information',
        Str('pw_name'),
        Str('pw_gecos'),
        Str('pw_dir'),
        Str('pw_shell'),
        Int('pw_uid'),
        Int('pw_gid'),
    ))
    async def get_user_obj(self, data):
        """
        Returns dictionary containing information from struct passwd for the user specified by either
        the username or uid. Bypasses user cache.
        """
        verrors = ValidationErrors()
        if not data['username'] and data['uid'] is None:
            verrors.add('get_user_obj.username', 'Either "username" or "uid" must be specified')
        verrors.check()
        return await self.middleware.call('dscache.get_uncached_user', data['username'], data['uid'])

    @item_method
    @accepts(
        Int('id'),
        Str('key'),
        Any('value'),
    )
    @returns(Bool())
    async def set_attribute(self, pk, key, value):
        """
        Set user general purpose `attributes` dictionary `key` to `value`.

        e.g. Setting key="foo" value="var" will result in {"attributes": {"foo": "bar"}}
        """
        user = await self._get_instance(pk)

        user['attributes'][key] = value

        await self.middleware.call(
            'datastore.update',
            'account.bsdusers',
            pk,
            {'attributes': user['attributes']},
            {'prefix': 'bsdusr_'}
        )

        return True

    @item_method
    @accepts(
        Int('id'),
        Str('key'),
    )
    @returns(Bool())
    async def pop_attribute(self, pk, key):
        """
        Remove user general purpose `attributes` dictionary `key`.
        """
        user = await self._get_instance(pk)

        if key in user['attributes']:
            user['attributes'].pop(key)

            await self.middleware.call(
                'datastore.update',
                'account.bsdusers',
                pk,
                {'attributes': user['attributes']},
                {'prefix': 'bsdusr_'}
            )
            return True
        else:
            return False

    @accepts()
    @returns(Int('next_available_uid'))
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

            if i['uid'] > last_uid:
                last_uid = i['uid']

        return last_uid + 1

    @no_auth_required
    @accepts()
    @returns(Bool())
    async def has_root_password(self):
        """
        Return whether the root user has a valid password set.

        This is used when the system is installed without a password and must be set on
        first use/login.
        """
        return (await self.middleware.call(
            'datastore.query', 'account.bsdusers', [('bsdusr_username', '=', 'root')], {'get': True}
        ))['bsdusr_unixhash'] != '*'

    @no_auth_required
    @accepts(
        Str('password'),
        Dict(
            'options',
            Dict(
                'ec2',
                Str('instance_id', required=True),
            ),
            update=True,
        )
    )
    @returns()
    @pass_app()
    async def set_root_password(self, app, password, options):
        """
        Set password for root user if it is not already set.
        """
        if not app.authenticated:
            if await self.middleware.call('user.has_root_password'):
                raise CallError('You cannot call this method anonymously if root already has a password', errno.EACCES)

            if await self.middleware.call('system.environment') == 'EC2':
                if 'ec2' not in options:
                    raise CallError(
                        'You need to specify instance ID when setting initial root password on EC2 instance',
                        errno.EACCES,
                    )

                if options['ec2']['instance_id'] != await self.middleware.call('ec2.instance_id'):
                    raise CallError('Incorrect EC2 instance ID', errno.EACCES)

        root = await self.middleware.call('user.query', [('username', '=', 'root')], {'get': True})
        await self.middleware.call('user.update', root['id'], {'password': password})

    @private
    @job(lock=lambda args: f'copy_home_to_{args[1]}')
    async def do_home_copy(self, job, home_old, home_new, username, new_mode, uid):
        if new_mode is not None:
            perm_job = await self.middleware.call('filesystem.setperm', {
                'uid': uid,
                'path': home_new,
                'mode': new_mode,
                'options': {'stripacl': True},
            })
            await perm_job.wait()

        if home_old == '/nonexistent':
            return

        command = f"/bin/cp -a {shlex.quote(home_old) + '/'} {shlex.quote(home_new + '/')}"
        do_copy = await run(["/usr/bin/su", "-", username, "-c", command], check=False)
        if do_copy.returncode != 0:
            raise CallError(f"Failed to copy homedir [{home_old}] to [{home_new}]: {do_copy.stderr.decode()}")

    async def __common_validation(self, verrors, data, schema, pk=None):

        exclude_filter = [('id', '!=', pk)] if pk else []

        if 'username' in data:
            pw_checkname(verrors, f'{schema}.username', data['username'])

            if await self.middleware.call('datastore.query', 'account.bsdusers', [
                ('username', '=', data['username'])
            ] + exclude_filter, {'prefix': 'bsdusr_'}):
                verrors.add(
                    f'{schema}.username',
                    f'The username "{data["username"]}" already exists.',
                    errno.EEXIST
                )
            if data.get('smb'):
                smb_users = await self.middleware.call('datastore.query',
                                                       'account.bsdusers',
                                                       [('smb', '=', True)] + exclude_filter,
                                                       {'prefix': 'bsdusr_'})

                if any(filter(lambda x: data['username'].casefold() == x['username'].casefold(), smb_users)):
                    verrors.add(
                        f'{schema}.smb',
                        f'Username "{data["username"]}" conflicts with existing SMB user. Note that SMB '
                        f'usernames are case-insensitive.',
                        errno.EEXIST,
                    )

        password = data.get('password')
        if password and '?' in password:
            # See bug #4098
            verrors.add(
                f'{schema}.password',
                'An SMB issue prevents creating passwords containing a '
                'question mark (?).',
                errno.EINVAL
            )
        elif not pk and not password and not data.get('password_disabled'):
            verrors.add(f'{schema}.password', 'Password is required')
        elif data.get('password_disabled') and password:
            verrors.add(
                f'{schema}.password_disabled',
                'Leave "Password" blank when "Disable password login" is checked.'
            )

        if 'home' in data:
            p = Path(data['home'])
            if not p.is_absolute():
                verrors.add(f'{schema}.home', '"Home Directory" must be an absolute path.')
                return

            if p.is_file():
                verrors.add(f'{schema}.home', '"Home Directory" cannot be a file.')
                return

            if ':' in data['home']:
                verrors.add(f'{schema}.home', '"Home Directory" cannot contain colons (:).')

            if data['home'] != '/nonexistent':
                if not data['home'].startswith('/mnt/'):
                    verrors.add(
                        f'{schema}.home',
                        '"Home Directory" must begin with /mnt/ or set to '
                        '/nonexistent.'
                    )
                elif not any(
                    data['home'] == i['path'] or data['home'].startswith(i['path'] + '/')
                    for i in await self.middleware.call('pool.query')
                ):
                    verrors.add(
                        f'{schema}.home',
                        f'The path for the home directory "({data["home"]})" '
                        'must include a volume or dataset.'
                    )
                elif await self.middleware.call('pool.dataset.path_in_locked_datasets', data['home']):
                    verrors.add(
                        f'{schema}.home',
                        'Path component for "Home Directory" is currently encrypted and locked'
                    )
                elif len(p.resolve().parents) == 2:
                    verrors.add(
                        f'{schema}.home',
                        f'The specified path is a ZFS pool mountpoint "({data["home"]})" '
                    )

        if 'home_mode' in data:
            try:
                o = int(data['home_mode'], 8)
                assert o & 0o777 == o
                if o & (stat.S_IRUSR) == 0:
                    verrors.add(
                        f'{schema}.home_mode',
                        'Home directory must be readable by User.'
                    )
                if o & (stat.S_IXUSR) == 0:
                    verrors.add(
                        f'{schema}.home_mode',
                        'Home directory must be executable by User.'
                    )
            except (AssertionError, ValueError, TypeError):
                verrors.add(
                    f'{schema}.home_mode',
                    'Please provide a valid value for home_mode attribute'
                )

        if 'groups' in data:
            groups = data.get('groups') or []
            if groups and len(groups) > 64:
                verrors.add(
                    f'{schema}.groups',
                    'A user cannot belong to more than 64 auxiliary groups.'
                )

        if 'full_name' in data and ':' in data['full_name']:
            verrors.add(
                f'{schema}.full_name',
                'The ":" character is not allowed in a "Full Name".'
            )

        if 'shell' in data and data['shell'] not in await self.middleware.call('user.shell_choices', pk):
            verrors.add(
                f'{schema}.shell', 'Please select a valid shell.'
            )

        if 'sudo_commands' in data:
            verrors.add_child(
                f'{schema}.sudo_commands',
                await self.middleware.run_in_thread(validate_sudo_commands, data['sudo_commands']),
            )

    async def __set_password(self, data):
        if 'password' not in data:
            return
        password = data.pop('password')
        if password:
            data['unixhash'] = crypted_password(password)
            # See http://samba.org.ru/samba/docs/man/manpages/smbpasswd.5.html
            data['smbhash'] = f'{data["username"]}:{data["uid"]}:{"X" * 32}:{nt_password(password)}:[U         ]:LCT-{int(time.time()):X}:'
        else:
            data['unixhash'] = '*'
            data['smbhash'] = '*'
        return password

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

    @private
    async def update_sshpubkey(self, homedir, user, group):
        if 'sshpubkey' not in user:
            return
        if not os.path.isdir(homedir):
            return

        sshpath = f'{homedir}/.ssh'
        keysfile = f'{sshpath}/authorized_keys'
        gid = -1

        pubkey = user.get('sshpubkey') or ''
        pubkey = pubkey.strip()
        if pubkey == '':
            try:
                os.unlink(keysfile)
            except OSError:
                pass
            return

        oldpubkey = ''
        try:
            with open(keysfile, 'r') as f:
                oldpubkey = f.read().strip()
        except Exception:
            pass

        if pubkey == oldpubkey:
            return

        if not os.path.isdir(sshpath):
            os.mkdir(sshpath, mode=0o700)
        if not os.path.isdir(sshpath):
            raise CallError(f'{sshpath} is not a directory')

        # Make extra sure to enforce correct mode on .ssh directory.
        # stripping the ACL will allow subsequent chmod calls to succeed even if
        # dataset aclmode is restricted.
        try:
            gid = (await self.middleware.call('group.get_group_obj', {'groupname': group}))['gr_gid']
        except Exception:
            # leaving gid at -1 avoids altering the GID value.
            self.logger.debug("Failed to convert %s to gid", group, exc_info=True)

        await self.middleware.call('filesystem.setperm', {
            'path': sshpath,
            'mode': str(700),
            'uid': user['uid'],
            'gid': gid,
            'options': {'recursive': True, 'stripacl': True}
        })

        with open(keysfile, 'w') as f:
            f.write(pubkey)
            f.write('\n')
        await self.middleware.call('filesystem.setperm', {'path': keysfile, 'mode': str(600)})


class GroupModel(sa.Model):
    __tablename__ = 'account_bsdgroups'

    id = sa.Column(sa.Integer(), primary_key=True)
    bsdgrp_gid = sa.Column(sa.Integer())
    bsdgrp_group = sa.Column(sa.String(120), unique=True)
    bsdgrp_builtin = sa.Column(sa.Boolean(), default=False)
    bsdgrp_sudo = sa.Column(sa.Boolean(), default=False)
    bsdgrp_sudo_nopasswd = sa.Column(sa.Boolean())
    bsdgrp_sudo_commands = sa.Column(sa.JSON(type=list))
    bsdgrp_smb = sa.Column(sa.Boolean(), default=True)


class GroupMembershipModel(sa.Model):
    __tablename__ = 'account_bsdgroupmembership'

    id = sa.Column(sa.Integer(), primary_key=True)
    bsdgrpmember_group_id = sa.Column(sa.Integer(), sa.ForeignKey("account_bsdgroups.id", ondelete="CASCADE"))
    bsdgrpmember_user_id = sa.Column(sa.Integer(), sa.ForeignKey("account_bsdusers.id", ondelete="CASCADE"))


class GroupService(CRUDService):

    class Config:
        datastore = 'account.bsdgroups'
        datastore_prefix = 'bsdgrp_'
        datastore_extend = 'group.group_extend'
        cli_namespace = 'account.group'

    ENTRY = Patch(
        'group_create', 'group_entry',
        ('rm', {'name': 'name'}),
        ('rm', {'name': 'allow_duplicate_gid'}),
        ('add', Int('id')),
        ('add', Str('group')),
        ('add', Bool('builtin')),
        ('add', Bool('id_type_both')),
        ('add', Bool('local')),
    )

    @private
    async def group_extend(self, group):
        # Get group membership
        group['users'] = [gm['user']['id'] for gm in await self.middleware.call('datastore.query', 'account.bsdgroupmembership', [('group', '=', group['id'])], {'prefix': 'bsdgrpmember_'})]
        group['users'] += [gmu['id'] for gmu in await self.middleware.call('datastore.query', 'account.bsdusers', [('bsdusr_group_id', '=', group['id'])])]
        return group

    @private
    async def group_compress(self, group):
        if 'local' in group:
            group.pop('local')
        if 'id_type_both' in group:
            group.pop('id_type_both')
        return group

    @filterable
    async def query(self, filters, options):
        """
        Query groups with `query-filters` and `query-options`. As a performance optimization, only local groups
        will be queried by default.

        Groups from directory services such as NIS, LDAP, or Active Directory will be included in query results
        if the option `{'extra': {'search_dscache': True}}` is specified.
        """
        if not filters:
            filters = []

        options = options or {}
        options['extend'] = self._config.datastore_extend
        options['extend_context'] = self._config.datastore_extend_context
        options['prefix'] = self._config.datastore_prefix

        datastore_options = options.copy()
        datastore_options.pop('count', None)
        datastore_options.pop('get', None)
        datastore_options.pop('limit', None)
        datastore_options.pop('offset', None)

        extra = options.get('extra', {})
        dssearch = extra.pop('search_dscache', False)

        if dssearch:
            return await self.middleware.call('dscache.query', 'GROUPS', filters, options)

        result = await self.middleware.call(
            'datastore.query', self._config.datastore, [], datastore_options
        )
        for entry in result:
            entry.update({'local': True, 'id_type_both': False})
        return await self.middleware.run_in_thread(
            filter_list, result, filters, options
        )

    @accepts(Dict(
        'group_create',
        Int('gid'),
        Str('name', required=True),
        Bool('smb', default=True),
        Bool('sudo', default=False),
        Bool('sudo_nopasswd', default=False),
        List('sudo_commands', items=[Str('command', empty=False)]),
        Bool('allow_duplicate_gid', default=False),
        List('users', items=[Int('id')], required=False),
        register=True,
    ))
    @returns(Int('primary_key'))
    async def do_create(self, data):
        """
        Create a new group.

        If `gid` is not provided it is automatically filled with the next one available.

        `allow_duplicate_gid` allows distinct group names to share the same gid.

        `users` is a list of user ids (`id` attribute from `user.query`).

        `smb` specifies whether the group should be mapped into an NT group.
        """
        return await self.create_internal(data)

    @private
    async def create_internal(self, data, reload_users=True):

        verrors = ValidationErrors()
        await self.__common_validation(verrors, data, 'group_create')
        verrors.check()

        if not data.get('gid'):
            data['gid'] = await self.get_next_gid()

        group = data.copy()
        group['group'] = group.pop('name')

        users = group.pop('users', [])

        group = await self.group_compress(group)
        pk = await self.middleware.call('datastore.insert', 'account.bsdgroups', group, {'prefix': 'bsdgrp_'})

        for user in users:
            await self.middleware.call('datastore.insert', 'account.bsdgroupmembership', {'bsdgrpmember_group': pk, 'bsdgrpmember_user': user})

        if reload_users:
            await self.middleware.call('service.reload', 'user')

        if data['smb']:
            await self.middleware.call('smb.synchronize_group_mappings')

        return pk

    @accepts(
        Int('id'),
        Patch(
            'group_create',
            'group_update',
            ('attr', {'update': True}),
        ),
    )
    @returns(Int('primary_key'))
    async def do_update(self, pk, data):
        """
        Update attributes of an existing group.
        """

        group = await self._get_instance(pk)
        groupmap_changed = False

        verrors = ValidationErrors()
        await self.__common_validation(verrors, data, 'group_update', pk=pk)
        verrors.check()
        old_smb = group['smb']

        group.update(data)
        group.pop('users', None)
        new_smb = group['smb']

        if 'name' in data and data['name'] != group['group']:
            group['group'] = group.pop('name')
            if new_smb:
                groupmap_changed = True
        else:
            group.pop('name', None)
            if new_smb and not old_smb:
                groupmap_changed = True
            elif old_smb and not new_smb:
                groupmap_changed = True

        group = await self.group_compress(group)
        await self.middleware.call('datastore.update', 'account.bsdgroups', pk, group, {'prefix': 'bsdgrp_'})

        if 'users' in data:
            existing = {i['bsdgrpmember_user']['id']: i for i in await self.middleware.call('datastore.query', 'account.bsdgroupmembership', [('bsdgrpmember_group', '=', pk)])}
            to_remove = set(existing.keys()) - set(data['users'])
            for i in to_remove:
                await self.middleware.call('datastore.delete', 'account.bsdgroupmembership', existing[i]['id'])

            to_add = set(data['users']) - set(existing.keys())
            for i in to_add:
                await self.middleware.call('datastore.insert', 'account.bsdgroupmembership', {'bsdgrpmember_group': pk, 'bsdgrpmember_user': i})

        await self.middleware.call('service.reload', 'user')

        if groupmap_changed:
            await self.middleware.call('smb.synchronize_group_mappings')

        return pk

    @accepts(Int('id'), Dict('options', Bool('delete_users', default=False)))
    @returns(Int('primary_key'))
    async def do_delete(self, pk, options):
        """
        Delete group `id`.

        The `delete_users` option deletes all users that have this group as their primary group.
        """

        group = await self._get_instance(pk)
        if group['smb']:
            await self.middleware.call('smb.synchronize_group_mappings')

        if group['builtin']:
            raise CallError('A built-in group cannot be deleted.', errno.EACCES)

        nogroup = await self.middleware.call('datastore.query', 'account.bsdgroups', [('group', '=', 'nogroup')],
                                             {'prefix': 'bsdgrp_', 'get': True})
        for i in await self.middleware.call('datastore.query', 'account.bsdusers', [('group', '=', group['id'])],
                                            {'prefix': 'bsdusr_'}):
            if options['delete_users']:
                await self.middleware.call('datastore.delete', 'account.bsdusers', i['id'])
            else:
                await self.middleware.call('datastore.update', 'account.bsdusers', i['id'], {'group': nogroup['id']},
                                           {'prefix': 'bsdusr_'})

        await self.middleware.call('datastore.delete', 'account.bsdgroups', pk)

        await self.middleware.call('service.reload', 'user')

        return pk

    @accepts()
    @returns(Int('next_available_gid'))
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

            if i['gid'] > last_gid:
                last_gid = i['gid']

        return last_gid + 1

    @accepts(Dict(
        'get_group_obj',
        Str('groupname', default=None),
        Int('gid', default=None)
    ))
    @returns(Dict(
        'group_info',
        Str('gr_name'),
        Int('gr_gid'),
        List('gr_mem'),
    ))
    async def get_group_obj(self, data):
        """
        Returns dictionary containing information from struct grp for the group specified by either
        the groupname or gid. Bypasses group cache.
        """
        verrors = ValidationErrors()
        if not data['groupname'] and data['gid'] is None:
            verrors.add('get_group_obj.groupname', 'Either "groupname" or "gid" must be specified')
        verrors.check()
        return await self.middleware.call('dscache.get_uncached_group', data['groupname'], data['gid'])

    async def __common_validation(self, verrors, data, schema, pk=None):

        exclude_filter = [('id', '!=', pk)] if pk else []

        if 'name' in data:
            if data.get('smb'):
                if data['name'].upper() in [x.name for x in SMBBuiltin]:
                    verrors.add(
                        f'{schema}.name',
                        f'Group name "{data["name"]}" conflicts with existing SMB Builtin entry. '
                        f'SMB group mapping is not permitted for this group.',
                        errno.EEXIST,
                    )

                smb_groups = await self.middleware.call('datastore.query',
                                                        'account.bsdgroups',
                                                        [('smb', '=', True)] + exclude_filter,
                                                        {'prefix': 'bsdgrp_'})

                if any(filter(lambda x: data['name'].casefold() == x['group'].casefold(), smb_groups)):
                    verrors.add(
                        f'{schema}.name',
                        f'Group name "{data["name"]}" conflicts with existing groupmap entry. '
                        f'SMB group mapping is not permitted for this group. Note that SMB '
                        f'group names are case-insensitive.',
                        errno.EEXIST,
                    )

            existing = await self.middleware.call('datastore.query', 'account.bsdgroups', [('group', '=', data['name'])] + exclude_filter, {'prefix': 'bsdgrp_'})
            if existing:
                verrors.add(
                    f'{schema}.name',
                    f'A Group with the name "{data["name"]}" already exists.',
                    errno.EEXIST,
                )

            pw_checkname(verrors, f'{schema}.name', data['name'])

        allow_duplicate_gid = data.pop('allow_duplicate_gid', False)
        if data.get('gid') and not allow_duplicate_gid:
            existing = await self.middleware.call('datastore.query', 'account.bsdgroups', [('gid', '=', data['gid'])] + exclude_filter, {'prefix': 'bsdgrp_'})
            if existing:
                verrors.add(
                    f'{schema}.gid',
                    f'The Group ID "{data["gid"]}" already exists.',
                    errno.EEXIST,
                )

        if 'users' in data:
            existing = set([i['id'] for i in await self.middleware.call('datastore.query', 'account.bsdusers', [('id', 'in', data['users'])])])
            notfound = set(data['users']) - existing
            if notfound:
                verrors.add(
                    f'{schema}.users',
                    f'Following users do not exist: {", ".join(map(str, notfound))}',
                )

        if 'sudo_commands' in data:
            verrors.add_child(
                f'{schema}.sudo_commands',
                await self.middleware.run_in_thread(validate_sudo_commands, data['sudo_commands']),
            )


async def setup(middleware):
    if await middleware.call('keyvalue.get', 'run_migration', False):
        await middleware.call('user.sync_builtin')
