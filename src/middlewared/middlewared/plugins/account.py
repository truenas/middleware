import binascii
import errno
import glob
import hashlib
import json
import os
import shlex
import shutil
import stat
import subprocess
import time
import warnings
import wbclient
from pathlib import Path
from contextlib import suppress

from middlewared.schema import accepts, Bool, Dict, Int, List, Password, Patch, returns, SID, Str, LocalUsername
from middlewared.service import (
    CallError, CRUDService, ValidationErrors, no_auth_required, no_authz_required, pass_app, private, filterable, job
)
from middlewared.service_exception import MatchNotFound
import middlewared.sqlalchemy as sa
from middlewared.utils import run, filter_list
from middlewared.utils.crypto import sha512_crypt
from middlewared.utils.nss import pwd, grp
from middlewared.utils.nss.nss_common import NssModule
from middlewared.utils.privilege import credential_has_full_admin, privileges_group_mapping
from middlewared.validators import Email, Range
from middlewared.async_validators import check_path_resides_within_volume
from middlewared.plugins.smb_.constants import SMBBuiltin
from middlewared.plugins.idmap_.idmap_constants import (
    TRUENAS_IDMAP_DEFAULT_LOW,
    SID_LOCAL_USER_PREFIX,
    SID_LOCAL_GROUP_PREFIX
)
from middlewared.plugins.idmap_ import idmap_winbind
from middlewared.plugins.idmap_ import idmap_sss

ADMIN_UID = 950  # When googled, does not conflict with anything
ADMIN_GID = 950
SKEL_PATH = '/etc/skel/'
# TrueNAS historically used /nonexistent as the default home directory for new
# users. The nonexistent directory has caused problems when
# 1) an admin chooses to create it from shell
# 2) PAM checks for home directory existence
# And so this default has been deprecated in favor of using /var/empty
# which is an empty and immutable directory.
LEGACY_DEFAULT_HOME_PATH = '/nonexistent'
DEFAULT_HOME_PATH = '/var/empty'
DEFAULT_HOME_PATHS = (DEFAULT_HOME_PATH, LEGACY_DEFAULT_HOME_PATH)


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


def crypted_password(cleartext, algo='SHA512'):
    if algo == 'SHA512':
        return sha512_crypt(cleartext)
    else:
        raise ValueError(f'{algo} is unsupported')


def unixhash_is_valid(unixhash):
    return unixhash not in ("x", "*")


def nt_password(cleartext):
    nthash = hashlib.new('md4', cleartext.encode('utf-16le')).digest()
    return binascii.hexlify(nthash).decode().upper()


def validate_sudo_commands(commands):
    verrors = ValidationErrors()
    if 'ALL' in commands and len(commands) != 1:
        verrors.add(str(commands.index('ALL')), 'ALL cannot be used with other commands')
        return verrors

    for i, command in enumerate(commands):
        try:
            executable = shlex.split(command)[0]

            if executable == 'ALL':
                continue

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
    bsdusr_home = sa.Column(sa.String(255), default=DEFAULT_HOME_PATH)
    bsdusr_shell = sa.Column(sa.String(120), default='/bin/csh')
    bsdusr_full_name = sa.Column(sa.String(120))
    bsdusr_builtin = sa.Column(sa.Boolean(), default=False)
    bsdusr_smb = sa.Column(sa.Boolean(), default=True)
    bsdusr_password_disabled = sa.Column(sa.Boolean(), default=False)
    bsdusr_ssh_password_enabled = sa.Column(sa.Boolean(), default=False)
    bsdusr_locked = sa.Column(sa.Boolean(), default=False)
    bsdusr_sudo_commands = sa.Column(sa.JSON(list))
    bsdusr_sudo_commands_nopasswd = sa.Column(sa.JSON(list))
    bsdusr_group_id = sa.Column(sa.ForeignKey('account_bsdgroups.id'), index=True)
    bsdusr_email = sa.Column(sa.String(254), nullable=True)


class UserService(CRUDService):
    """
    Manage local users
    """

    class Config:
        datastore = 'account.bsdusers'
        datastore_extend = 'user.user_extend'
        datastore_extend_context = 'user.user_extend_context'
        datastore_prefix = 'bsdusr_'
        cli_namespace = 'account.user'
        role_prefix = 'ACCOUNT'

    # FIXME: Please see if dscache can potentially alter result(s) format, without ad, it doesn't seem to
    ENTRY = Patch(
        'user_create', 'user_entry',
        ('rm', {'name': 'group'}),
        ('rm', {'name': 'group_create'}),
        ('rm', {'name': 'home_mode'}),
        ('rm', {'name': 'home_create'}),
        ('rm', {'name': 'password'}),
        ('add', Dict('group', additional_attrs=True)),
        ('add', Int('id')),
        ('add', Bool('builtin')),
        ('add', Bool('id_type_both')),
        ('add', Bool('local')),
        ('add', Bool('immutable')),
        ('add', Bool('twofactor_auth_configured')),
        ('add', Str('unixhash', private=True)),
        ('add', Str('smbhash', private=True)),
        ('add', Str('nt_name', null=True)),
        ('add', Str('sid', null=True)),
        ('add', List('roles', items=[Str('role')])),
    )

    @private
    async def user_extend_context(self, rows, extra):
        memberships = {}
        res = await self.middleware.call(
            'datastore.query', 'account.bsdgroupmembership',
            [], {'prefix': 'bsdgrpmember_'}
        )

        group_roles = await self.middleware.call('group.query', [], {'select': ['id', 'roles']})

        for i in res:
            uid = i['user']['id']
            if uid in memberships:
                memberships[uid].append(i['group']['id'])
            else:
                memberships[uid] = [i['group']['id']]

        return {
            'memberships': memberships,
            'user_2fa_mapping': ({
                entry['user']['id']: bool(entry['secret']) for entry in await self.middleware.call(
                    'datastore.query', 'account.twofactor_user_auth', [['user_id', '!=', None]]
                )
            }),
            'roles_mapping': {i['id']: i['roles'] for i in group_roles}
        }

    @private
    def _read_authorized_keys(self, homedir):
        with suppress(FileNotFoundError):
            with open(f'{homedir}/.ssh/authorized_keys') as f:
                return f.read().strip()

    @private
    async def user_extend(self, user, ctx):

        # Normalize email, empty is really null
        if user['email'] == '':
            user['email'] = None

        user['groups'] = ctx['memberships'].get(user['id'], [])
        # Get authorized keys
        user['sshpubkey'] = await self.middleware.run_in_thread(self._read_authorized_keys, user['home'])

        user['immutable'] = user['builtin'] or (user['username'] == 'admin' and user['home'] == '/home/admin')
        user['twofactor_auth_configured'] = bool(ctx['user_2fa_mapping'][user['id']])

        user_roles = set()
        for g in user['groups'] + [user['group']['id']]:
            if not (entry := ctx['roles_mapping'].get(g)):
                continue

            user_roles |= set(entry)

        user.update({
            'local': True,
            'id_type_both': False,
            'nt_name': None,
            'sid': None,
            'roles': list(user_roles)
        })
        return user

    @private
    def user_compress(self, user):
        to_remove = [
            'local',
            'id_type_both',
            'nt_name',
            'sid',
            'immutable',
            'home_create',
            'roles',
            'twofactor_auth_configured',
        ]

        for i in to_remove:
            user.pop(i, None)

        return user

    @filterable
    async def query(self, filters, options):
        """
        Query users with `query-filters` and `query-options`. As a performance optimization, only local users
        will be queried by default.

        Expanded information may be requested by specifying the extra option
        `"extra": {"additional_information": []}`.

        The following `additional_information` options are supported:
        `SMB` - include Windows SID and NT Name for user. If this option is not specified, then these
            keys will have `null` value.
        `DS` - include users from Directory Service (LDAP or Active Directory) in results

        `"extra": {"search_dscache": true}` is a legacy method of querying for directory services users.
        """
        ds_users = []
        options = options or {}
        options['extend'] = self._config.datastore_extend
        options['extend_context'] = self._config.datastore_extend_context
        options['prefix'] = self._config.datastore_prefix

        datastore_options = options.copy()
        datastore_options.pop('count', None)
        datastore_options.pop('get', None)
        datastore_options.pop('limit', None)
        datastore_options.pop('offset', None)
        datastore_options.pop('select', None)

        extra = options.get('extra', {})
        dssearch = extra.pop('search_dscache', False)
        additional_information = extra.get('additional_information', [])

        if 'DS' in additional_information:
            dssearch = True
            additional_information.remove('DS')

        username_sid = {}
        if 'SMB' in additional_information:
            try:
                for u in await self.middleware.call("smb.passdb_list", True):
                    username_sid.update({u['Unix username']: {
                        'nt_name': u['NT username'],
                        'sid': u['User SID'],
                    }})
            except Exception:
                # Failure to retrieve passdb list often means that system dataset is
                # broken
                self.logger.error('Failed to retrieve passdb information', exc_info=True)

        if dssearch:
            ds_state = await self.middleware.call('directoryservices.get_state')
            if ds_state['activedirectory'] == 'HEALTHY' or ds_state['ldap'] == 'HEALTHY':
                ds_users = await self.middleware.call('directoryservices.cache.query', 'USERS', filters, options.copy())
                # For AD users, we will not have 2FA attribute normalized so let's do that
                ad_users_2fa_mapping = await self.middleware.call('auth.twofactor.get_ad_users')
                for index, user in enumerate(filter(
                    lambda u: not u['local'] and 'twofactor_auth_configured' not in u, ds_users)
                ):
                    ds_users[index]['twofactor_auth_configured'] = bool(ad_users_2fa_mapping.get(user['sid']))

        result = await self.middleware.call(
            'datastore.query', self._config.datastore, [], datastore_options
        )

        if username_sid:
            for entry in result:
                smb_entry = username_sid.get(entry['username'], {
                    'nt_name': '',
                    'sid': '',
                })
                if smb_entry['sid']:
                    smb_entry['nt_name'] = smb_entry['nt_name'] or entry['username']

                entry.update(smb_entry)

        return await self.middleware.run_in_thread(
            filter_list, result + ds_users, filters, options
        )

    @private
    def validate_homedir_mountinfo(self, verrors, schema, dev):
        mntinfo = self.middleware.call_sync(
            'filesystem.mount_info',
            [['device_id.dev_t', '=', dev]],
            {'get': True}
        )

        if 'RO' in mntinfo['mount_opts']:
            verrors.add(f'{schema}.home', 'Path has the ZFS readonly property set.')
            return False

        if mntinfo['fs_type'] != 'zfs':
            verrors.add(f'{schema}.home', 'Path is not on a ZFS filesystem')
            return False

        return True

    @private
    def validate_homedir_path(self, verrors, schema, data, users):
        p = Path(data['home'])

        if not p.is_absolute():
            verrors.add(f'{schema}.home', '"Home Directory" must be an absolute path.')
            return False

        if p.is_file():
            verrors.add(f'{schema}.home', '"Home Directory" cannot be a file.')
            return False

        if ':' in data['home']:
            verrors.add(f'{schema}.home', '"Home Directory" cannot contain colons (:).')
            return False

        if data['home'] in DEFAULT_HOME_PATHS:
            return False

        if not p.exists():
            if data.get('home_create', False):
                verrors.add(
                    f'{schema}.home',
                    f'{data["home"]}: path specified to use for home directory creation does not '
                    'exist. TrueNAS uses the provided path as the parent directory of the '
                    'newly-created home directory.'
                )

            else:
                verrors.add(
                    f'{schema}.home',
                    f'{data["home"]}: path specified to use as home directory does not exist.'
                )

            if not p.parent.exists():
                verrors.add(
                    f'{schema}.home',
                    f'{p.parent}: parent path of specified home directory does not exist.'
                )

            if not verrors:
                self.validate_homedir_mountinfo(verrors, schema, p.parent.stat().st_dev)

        elif self.validate_homedir_mountinfo(verrors, schema, p.stat().st_dev):
            if self.middleware.call_sync('filesystem.is_immutable', data['home']):
                verrors.add(
                    f'{schema}.home',
                    f'{data["home"]}: home directory path is immutable.'
                )

        in_use = filter_list(users, [('home', '=', data['home'])])
        if in_use:
            verrors.add(
                f'{schema}.home',
                f'{data["home"]}: homedir already used by {in_use[0]["username"]}.',
                errno.EEXIST
            )

        if not data['home'].startswith('/mnt'):
            verrors.add(
                f'{schema}.home',
                '"Home Directory" must begin with /mnt or set to '
                f'{DEFAULT_HOME_PATH}.'
            )
        elif data['home'] in ('/mnt', '/mnt/'):
            verrors.add(
                f'{schema}.home',
                '"Home Directory" cannot be at root of "/mnt"'
            )

        if verrors:
            # if we're already going to error out, skip more expensive tests
            return False

        if not any(
            data['home'] == i['path'] or data['home'].startswith(i['path'] + '/')
            for i in self.middleware.call_sync('pool.query')
        ):
            verrors.add(
                f'{schema}.home',
                f'The path for the home directory "({data["home"]})" '
                'must include a volume or dataset.'
            )
        elif self.middleware.call_sync('pool.dataset.path_in_locked_datasets', data['home']):
            verrors.add(
                f'{schema}.home',
                'Path component for "Home Directory" is currently encrypted and locked'
            )
        elif len(p.resolve().parents) == 2 and not data.get('home_create'):
            verrors.add(
                f'{schema}.home',
                f'The specified path is a ZFS pool mountpoint "({data["home"]})".'
            )

        return p.exists() and not verrors

    @private
    def setup_homedir(self, path, username, mode, uid, gid, create=False):
        homedir_created = False

        if create:
            target = os.path.join(path, username)
            try:
                # We do not raise exception on chmod error here because the
                # target path may have RESTRICTED aclmode. Correct permissions
                # get set in below `filesystem.setperm` call which strips ACL
                # if present to strictly enforce `mode`.
                self.middleware.call_sync('filesystem.mkdir', {
                    'path': target,
                    'options': {'mode': mode, 'raise_chmod_error': False}
                })
            except CallError as e:
                if e.errno == errno.EEXIST and not os.path.isdir(target):
                    raise CallError(
                        'Path for home directory already '
                        'exists and is not a directory',
                        errno.EEXIST
                    )
            except OSError as oe:
                raise CallError(
                    'Failed to create the home directory '
                    f'({target}) for user: {oe}'
                )
            else:
                homedir_created = True
        else:
            target = path

        try:
            setperm_job = self.middleware.call_sync('filesystem.setperm', {
                'path': target,
                'mode': mode,
                'uid': uid,
                'gid': gid,
                'options': {'stripacl': True}
            })
            setperm_job.wait_sync(raise_error=True)
        except Exception:
            if homedir_created:
                shutil.rmtree(target)
            raise

        return target

    @accepts(Dict(
        'user_create',
        Int('uid', validators=[Range(0, TRUENAS_IDMAP_DEFAULT_LOW - 1)]),
        LocalUsername('username', required=True),
        Int('group'),
        Bool('group_create', default=False),
        Str('home', default=DEFAULT_HOME_PATH),
        Str('home_mode', default='700'),
        Bool('home_create', default=False),
        Str('shell', default='/usr/bin/zsh'),
        Str('full_name', required=True),
        Str('email', validators=[Email()], null=True, default=None),
        Password('password'),
        Bool('password_disabled', default=False),
        Bool('ssh_password_enabled', default=False),
        Bool('locked', default=False),
        Bool('smb', default=True),
        List('sudo_commands', items=[Str('command', empty=False)]),
        List('sudo_commands_nopasswd', items=[Str('command', empty=False)]),
        Str('sshpubkey', null=True, max_length=None),
        List('groups', items=[Int('group')]),
        register=True,
    ), audit='Create user', audit_extended=lambda data: data["username"])
    @returns(Int('primary_key'))
    def do_create(self, data):
        """
        Create a new user.

        If `uid` is not provided it is automatically filled with the next one available.

        `group` is required if `group_create` is false.

        `password` is required if `password_disabled` is false.

        Available choices for `shell` can be retrieved with `user.shell_choices`.

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
                'Enter either a group name or create a new group to '
                'continue.',
                errno.EINVAL
            )

        group_ids = []
        if data.get('group'):
            group_ids.append(data['group'])
        if data.get('groups'):
            group_ids.extend(data['groups'])

        self.middleware.call_sync('user.common_validation', verrors, data, 'user_create', group_ids)

        if data.get('sshpubkey') and not data['home'].startswith('/mnt'):
            verrors.add(
                'user_create.sshpubkey',
                'The home directory is not writable. Leave this field blank.'
            )

        verrors.check()

        groups = data.pop('groups')
        create = data.pop('group_create')
        group_created = False

        if create:
            group = self.middleware.call_sync('group.query', [('group', '=', data['username'])])
            if group:
                group = group[0]
            else:
                group = self.middleware.call_sync('group.create_internal', {
                    'name': data['username'],
                    'smb': False,
                    'sudo_commands': [],
                    'sudo_commands_nopasswd': [],
                    'allow_duplicate_gid': False
                }, False)
                group = self.middleware.call_sync('group.query', [('id', '=', group)])[0]
                group_created = True

            data['group'] = group['id']
        else:
            group = self.middleware.call_sync('group.query', [('id', '=', data['group'])])
            if not group:
                raise CallError(f'Group {data["group"]} not found')
            group = group[0]

        if data['smb']:
            groups.append((self.middleware.call_sync(
                'group.query', [('group', '=', 'builtin_users')], {'get': True},
            ))['id'])

        if data.get('uid') is None:
            data['uid'] = self.middleware.call_sync('user.get_next_uid')

        new_homedir = False
        home_mode = data.pop('home_mode')
        if data['home'] and data['home'] not in DEFAULT_HOME_PATHS:
            try:
                data['home'] = self.setup_homedir(
                    data['home'],
                    data['username'],
                    home_mode,
                    data['uid'],
                    group['gid'],
                    data['home_create']
                )
            except Exception:
                # Homedir setup failed, we should remove any auto-generated group
                if group_created:
                    self.middleware.call_sync('group.delete', data['group'])

                raise

        pk = None  # Make sure pk exists to rollback in case of an error
        data = self.user_compress(data)
        try:
            self.__set_password(data)
            sshpubkey = data.pop('sshpubkey', None)  # datastore does not have sshpubkey

            pk = self.middleware.call_sync('datastore.insert', 'account.bsdusers', data, {'prefix': 'bsdusr_'})
            self.middleware.call_sync(
                'datastore.insert', 'account.twofactor_user_auth', {
                    'secret': None,
                    'user': pk,
                }
            )

            self.__set_groups(pk, groups)

        except Exception:
            if pk is not None:
                self.middleware.call_sync('datastore.delete', 'account.bsdusers', pk)
            if new_homedir:
                # Be as atomic as possible when creating the user if
                # commands failed to execute cleanly.
                shutil.rmtree(data['home'])
            raise

        self.middleware.call_sync('service.reload', 'ssh')
        self.middleware.call_sync('service.reload', 'user')

        if data['smb']:
            gm_job = self.middleware.call_sync('smb.synchronize_passdb')
            gm_job.wait_sync()

        if os.path.isdir(SKEL_PATH) and os.path.exists(data['home']) and data['home'] not in DEFAULT_HOME_PATHS:
            for f in os.listdir(SKEL_PATH):
                if f.startswith('dot'):
                    dest_file = os.path.join(data['home'], f[3:])
                else:
                    dest_file = os.path.join(data['home'], f)
                if not os.path.exists(dest_file):
                    shutil.copyfile(os.path.join(SKEL_PATH, f), dest_file)
                    chown_job = self.middleware.call_sync('filesystem.chown', {
                        'path': dest_file,
                        'uid': data['uid'],
                        'gid': group['gid'],
                    })
                    chown_job.wait_sync()

            data['sshpubkey'] = sshpubkey
            try:
                self.update_sshpubkey(data['home'], data, group['group'])
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
        audit='Update user',
        audit_callback=True,
    )
    @returns(Int('primary_key'))
    @pass_app()
    def do_update(self, app, audit_callback, pk, data):
        """
        Update attributes of an existing user.
        """

        user = self.middleware.call_sync('user.get_instance', pk)
        audit_callback(user['username'])

        if app and app.authenticated_credentials.is_user_session:
            same_user_logged_in = user['username'] == (self.middleware.call_sync('auth.me', app=app))['pw_name']
        else:
            same_user_logged_in = False

        verrors = ValidationErrors()

        if data.get('password_disabled'):
            try:
                self.middleware.call_sync('privilege.before_user_password_disable', user)
            except CallError as e:
                verrors.add('user_update.password_disabled', e.errmsg)

        if 'group' in data:
            group = self.middleware.call_sync('datastore.query', 'account.bsdgroups', [
                ('id', '=', data['group'])
            ])
            if not group:
                verrors.add('user_update.group', f'Group {data["group"]} not found', errno.ENOENT)
            group = group[0]
        else:
            group = user['group']
            user['group'] = group['id']

        if same_user_logged_in and (
            self.middleware.call_sync('auth.twofactor.config')
        )['enabled'] and not user['twofactor_auth_configured'] and not data.get('renew_twofactor_secret'):
            verrors.add(
                'user_update.renew_twofactor_secret',
                'Two-factor authentication is enabled globally but not configured for this user.'
            )

        if data.get('uid') == user['uid']:
            data.pop('uid')  # Only check for duplicate UID if we are updating it

        group_ids = [group['id']]
        if data.get('groups'):
            group_ids.extend(data['groups'])
        else:
            group_ids.extend(user['groups'])

        self.middleware.call_sync('user.common_validation', verrors, data, 'user_update', group_ids, user)

        try:
            st = os.stat(user.get("home", DEFAULT_HOME_PATH)).st_mode
            old_mode = f'{stat.S_IMODE(st):03o}'
        except FileNotFoundError:
            old_mode = None

        home = data.get('home') or user['home']
        had_home = user['home'] not in DEFAULT_HOME_PATHS
        has_home = home not in DEFAULT_HOME_PATHS
        # root user and admin users are an exception to the rule
        if data.get('sshpubkey'):
            if not (
                home in ['/home/admin', '/root'] or
                self.middleware.call_sync('filesystem.is_dataset_path', home)
            ):
                verrors.add('user_update.sshpubkey', 'Home directory is not writable, leave this blank"')

        # Do not allow attributes to be changed for builtin user
        if user['immutable']:
            if 'home_mode' in data:
                verrors.add('user_update.home_mode', 'This attribute cannot be changed')

            for i in ('group', 'home', 'uid', 'username', 'smb'):
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
                        self.middleware.call_sync("smb.remove_passdb_user", old_val)
                    except Exception:
                        self.logger.debug("Failed to remove passdb entry for user [%s]",
                                          old_val, exc_info=True)

                must_change_pdb_entry = True

        if user['smb'] is True and data.get('smb') is False:
            try:
                must_change_pdb_entry = False
                self.middleware.call_sync("smb.remove_passdb_user", user['username'])
            except Exception:
                self.logger.debug("Failed to remove passdb entry for user [%s]",
                                  user['username'], exc_info=True)

        if user['smb'] is False and data.get('smb') is True:
            must_change_pdb_entry = True

        # Copy the home directory if it changed
        home_copy = False
        home_old = None
        if (
            has_home and
            'home' in data and
            data['home'] != user['home'] and
            not data['home'].startswith(f'{user["home"]}/')
        ):
            if had_home:
                home_copy = True
                home_old = user['home']
            if data.get('home_create', False):
                data['home'] = os.path.join(data['home'], data.get('username') or user['username'])

        # After this point user dict has values from data
        user.update(data)

        mode_to_set = user.get('home_mode')
        if not mode_to_set:
            mode_to_set = '700' if old_mode is None else old_mode

        # squelch any potential problems when this occurs
        if has_home:
            self.middleware.call_sync('user.recreate_homedir_if_not_exists', user, group, mode_to_set)

        home_mode = user.pop('home_mode', None)
        if user['immutable']:
            home_mode = None

        try:
            update_sshpubkey_args = [
                home_old if home_copy else user['home'], user, group['bsdgrp_group'],
            ]
            self.update_sshpubkey(*update_sshpubkey_args)
        except PermissionError as e:
            self.logger.warn('Failed to update authorized keys', exc_info=True)
            raise CallError(f'Failed to update authorized keys: {e}')
        else:
            if user['uid'] == 0:
                if self.middleware.call_sync('failover.licensed'):
                    try:
                        self.middleware.call_sync(
                            'failover.call_remote', 'user.update_sshpubkey', update_sshpubkey_args
                        )
                    except Exception:
                        self.logger.error('Failed to sync root ssh pubkey to standby node', exc_info=True)

        if home_copy:
            """
            Background copy of user home directory to new path as the user in question.
            """
            self.middleware.call_sync(
                'user.do_home_copy', home_old, user['home'], user['username'], home_mode, user['uid']
            )

        elif has_home and home_mode is not None:
            """
            A non-recursive call to set permissions should return almost immediately.
            """
            perm_job = self.middleware.call_sync('filesystem.setperm', {
                'path': user['home'],
                'mode': home_mode,
                'options': {'stripacl': True},
            })
            perm_job.wait_sync()

        user.pop('sshpubkey', None)
        self.__set_password(user)

        if 'groups' in user:
            groups = user.pop('groups')
            self.__set_groups(pk, groups)

        user = self.user_compress(user)
        self.middleware.call_sync('datastore.update', 'account.bsdusers', pk, user, {'prefix': 'bsdusr_'})

        self.middleware.call_sync('service.reload', 'ssh')
        self.middleware.call_sync('service.reload', 'user')
        if user['smb'] and must_change_pdb_entry:
            gm_job = self.middleware.call_sync('smb.synchronize_passdb')
            gm_job.wait_sync()

        return pk

    @private
    def recreate_homedir_if_not_exists(self, user, group, mode):
        # sigh, nothing is stopping someone from removing the homedir
        # from the CLI so recreate the original directory in this case
        if not os.path.isdir(user['home']):
            if os.path.exists(user['home']):
                raise CallError(f'{user["home"]!r} already exists and is not a directory')

            self.logger.debug('Homedir %r for %r does not exist so recreating it', user['home'], user['username'])
            try:
                os.makedirs(user['home'])
            except Exception:
                raise CallError(f'Failed recreating "{user["home"]}"')
            else:
                self.middleware.call_sync('filesystem.setperm', {
                    'path': user['home'],
                    'uid': user['uid'],
                    'gid': group['bsdgrp_gid'],
                    'mode': mode,
                    'options': {'stripacl': True},
                }).wait_sync(raise_error=True)

    @accepts(
        Int('id'),
        Dict(
            'options',
            Bool('delete_group', default=True),
        ),
        audit='Delete user',
        audit_callback=True,
    )
    @returns(Int('primary_key'))
    def do_delete(self, audit_callback, pk, options):
        """
        Delete user `id`.

        The `delete_group` option deletes the user primary group if it is not being used by
        any other user.
        """

        user = self.middleware.call_sync('user.get_instance', pk)
        audit_callback(user['username'])

        if user['builtin']:
            raise CallError('Cannot delete a built-in user', errno.EINVAL)

        self.middleware.call_sync('privilege.before_user_delete', user)

        if options['delete_group'] and not user['group']['bsdgrp_builtin']:
            count = self.middleware.call_sync(
                'datastore.query', 'account.bsdgroupmembership',
                [('group', '=', user['group']['id'])], {'prefix': 'bsdgrpmember_', 'count': True}
            )
            count2 = self.middleware.call_sync(
                'datastore.query', 'account.bsdusers',
                [('group', '=', user['group']['id']), ('id', '!=', pk)], {'prefix': 'bsdusr_', 'count': True}
            )
            if count == 0 and count2 == 0:
                try:
                    self.middleware.call_sync('group.delete', user['group']['id'])
                except Exception:
                    self.logger.warn(f'Failed to delete primary group of {user["username"]}', exc_info=True)

        if user['home'] and user['home'] not in DEFAULT_HOME_PATHS:
            try:
                shutil.rmtree(os.path.join(user['home'], '.ssh'))
            except Exception:
                pass

        if user['smb']:
            subprocess.run(['smbpasswd', '-x', user['username']], capture_output=True)

        # TODO: add a hook in CIFS service
        cifs = self.middleware.call_sync('datastore.query', 'services.cifs', [], {'prefix': 'cifs_srv_'})
        if cifs:
            cifs = cifs[0]
            if cifs['guest'] == user['username']:
                self.middleware.call_sync(
                    'datastore.update', 'services.cifs', cifs['id'], {'guest': 'nobody'}, {'prefix': 'cifs_srv_'}
                )

        if attributes := self.middleware.call_sync('datastore.query', 'account.bsdusers_webui_attribute',
                                                   [['uid', '=', user['uid']]]):
            self.middleware.call_sync('datastore.delete', 'account.bsdusers_webui_attribute', attributes[0]['id'])

        self.middleware.call_sync('datastore.delete', 'account.bsdusers', pk)
        self.middleware.call_sync('service.reload', 'ssh')
        self.middleware.call_sync('service.reload', 'user')
        try:
            self.middleware.call_sync('idmap.gencache.del_idmap_cache_entry', {
                'entry_type': 'UID2SID',
                'entry': user['uid']
            })
        except MatchNotFound:
            pass

        return pk

    @accepts(List('group_ids', items=[Int('group_id')]))
    @returns(Dict(
        'shell_info',
        Str('shell_path'),
        example={
            '/usr/bin/bash': 'bash',
            '/usr/bin/rbash': 'rbash',
            '/usr/bin/dash': 'dash',
            '/usr/bin/sh': 'sh',
            '/usr/bin/zsh': 'zsh',
            '/usr/bin/tmux': 'tmux',
            '/usr/sbin/nologin': 'nologin'
        }
    ))
    def shell_choices(self, group_ids):
        """
        Return the available shell choices to be used in `user.create` and `user.update`.

        `group_ids` is a list of local group IDs for the user.
        """
        group_ids = {
            g["gid"] for g in self.middleware.call_sync(
                "datastore.query",
                "account.bsdgroups",
                [("id", "in", group_ids)],
                {"prefix": "bsdgrp_"},
            )
        }

        shells = {
            '/usr/sbin/nologin': 'nologin',
        }
        if self.middleware.call_sync('privilege.privileges_for_groups', 'local_groups', group_ids):
            shells.update(**{
                '/usr/bin/cli': 'TrueNAS CLI',  # installed via midcli
                '/usr/bin/cli_console': 'TrueNAS Console',  # installed via midcli
            })
        with open('/etc/shells') as f:
            for shell in filter(lambda x: x.startswith('/usr/bin'), f):
                # on scale /etc/shells has duplicate entries like (/bin/sh, /usr/bin/sh) (/bin/bash, /usr/bin/bash) etc.
                # The entries that point to the same basename are the same binary.
                # The /usr/bin/ path is the "newer" place to put binaries so we'll use those entries.
                shell = shell.strip()
                shells[shell] = os.path.basename(shell)

        return shells

    @accepts(Dict(
        'get_user_obj',
        Str('username', default=None),
        Int('uid', default=None),
        Bool('get_groups', default=False),
        Bool('sid_info', default=False),
    ), roles=['ACCOUNT_READ'])
    @returns(Dict(
        'user_information',
        Str('pw_name'),
        Str('pw_gecos'),
        Str('pw_dir'),
        Str('pw_shell'),
        Int('pw_uid'),
        Int('pw_gid'),
        List('grouplist'),
        SID('sid', null=True),
        Str('source', enum=[mod.name for mod in list(NssModule)]),
        Bool('local'),
        register=True,
    ))
    def get_user_obj(self, data):
        """
        Returns dictionary containing information from struct passwd for the user specified by either
        the username or uid. Bypasses user cache.

        Supports the following optional parameters:
        `get_groups` - retrieve group list for the specified user.

        NOTE: results will not include nested groups for Active Directory users

        `sid_info` - retrieve SID and domain information for the user

        Returns object with following keys:

        `pw_name` - name of the user

        `pw_uid` - numerical user id of the user

        `pw_gid` - numerical group id for the user's primary group

        `pw_gecos` - full username or comment field

        `pw_dir` - user home directory

        `pw_shell` - user command line interpreter

        `local` - boolean value indicating whether the account is local to TrueNAS or provided by
        a directory service.

        `grouplist` - optional list of group ids for groups of which this account is a member. If `get_groups`
        is not specified, this value will be null.

        `sid_info - optional dictionary object containing details of SID and domain information. If `sid_info`
        is not specified, this value will be null.

        NOTE: in some pathological scenarios this may make the operation hang until
        the winbindd request timeout has been reached if the winbindd connection manager
        has not yet marked the domain as offline. The TrueNAS middleware is more aggressive
        about marking AD domains as FAULTED and so it may be advisable to first check the
        Active Directory service state prior to batch operations using this option.
        """
        verrors = ValidationErrors()
        if not data['username'] and data['uid'] is None:
            verrors.add('get_user_obj.username', 'Either "username" or "uid" must be specified.')

        if data['username'] and data['uid'] is not None:
            verrors.add('get_user_obj.username', '"username" and "uid" may not be simultaneously specified')
        verrors.check()

        if data['username']:
            user_obj = pwd.getpwnam(data['username'], as_dict=True)
        else:
            user_obj = pwd.getpwuid(data['uid'], as_dict=True)

        user_obj['local'] = user_obj['source'] == 'FILES'

        if data['get_groups']:
            user_obj['grouplist'] = os.getgrouplist(user_obj['pw_name'], user_obj['pw_gid'])

        if data['sid_info']:
            match user_obj['source']:
                case NssModule.FILES.name | NssModule.WINBIND.name:
                    # winbind provides idmapping for local and AD users
                    try:
                        idmap_ctx = idmap_winbind.WBClient()
                    except wbclient.WBCError as e:
                        if e.error_code != wbclient.WBC_ERR_WINBIND_NOT_AVAILABLE:
                            self.logger.error('Failed to retrieve SID for uid: %d',
                                              user_obj['pw_uid'], exc_info=True)

                        idmap_ctx = None
                case NssModule.SSS.name:
                    # SSSD provides ID mapping for IPA domains
                    idmap_ctx = idmap_sss.SSSClient()
                case _:
                    # We're not raising an exception here since it
                    # can be a critical areai
                    self.logger.error(
                        '%s: unknown ID source. Please file a bug report.',
                        user_obj['source']
                    )
                    idmap_ctx = None

            if idmap_ctx is not None:
                try:
                    sid = idmap_ctx.uidgid_to_idmap_entry({
                        'id_type': 'USER',
                        'id': user_obj['pw_uid']
                    })['sid']
                except MatchNotFound:
                    if user_obj['source'] == NssModule.FILES.name:
                        # Local user that doesn't have passdb entry
                        # we can simply apply default prefix
                        sid = SID_LOCAL_USER_PREFIX + str(user_obj['pw_uid'])
                    else:
                        # This is a more odd situation. The user accout exists
                        # in IPA but doesn't have a SID assigned to it.
                        sid = None
            else:
                # We were unable to establish an idmap client context even
                # though we were able to retrieve the user account info. This
                # most likely means that we're dealing with a local account and
                # winbindd is not running.
                sid = None

            user_obj['sid'] = sid

        return user_obj

    @accepts(roles=['ACCOUNT_READ'])
    @returns(Int('next_available_uid'))
    async def get_next_uid(self):
        """
        Get the next available/free uid.
        """
        # We want to create new users from 3000 to avoid potential conflicts - Reference: NAS-117892
        last_uid = 2999
        builtins = await self.middleware.call(
            'datastore.query', 'account.bsdusers',
            [('builtin', '=', False)], {'order_by': ['uid'], 'prefix': 'bsdusr_'}
        )
        for i in builtins:
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
        Deprecated method. Use `user.has_local_administrator_set_up`
        """
        warnings.warn("`user.has_root_password` has been deprecated. Use `user.has_local_administrator_set_up`",
                      DeprecationWarning)
        return await self.has_local_administrator_set_up()

    @no_auth_required
    @accepts()
    @returns(Bool())
    async def has_local_administrator_set_up(self):
        """
        Return whether a local administrator with a valid password exists.

        This is used when the system is installed without a password and must be set on
        first use/login.
        """
        return len(await self.middleware.call('privilege.local_administrators')) > 0

    @no_auth_required
    @accepts(
        Password('password'),
        Dict('options')
    )
    @returns()
    @pass_app()
    async def set_root_password(self, app, password, options):
        """
        Deprecated method. Use `user.setup_local_administrator`
        """
        warnings.warn("`user.set_root_password` has been deprecated. Use `user.setup_local_administrator`",
                      DeprecationWarning)
        return await self.setup_local_administrator(app, 'root', password, options)

    @no_auth_required
    @accepts(
        Str('username', enum=['root', 'admin']),
        Password('password'),
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
    async def setup_local_administrator(self, app, username, password, options):
        """
        Set up local administrator (this method does not require authentication if local administrator is not already
        set up).
        """
        if not app.authenticated:
            if await self.middleware.call('system.environment') == 'EC2':
                if 'ec2' not in options:
                    raise CallError(
                        'You need to specify instance ID when setting up local administrator on EC2 instance',
                        errno.EACCES,
                    )

                if options['ec2']['instance_id'] != await self.middleware.call('ec2.instance_id'):
                    raise CallError('Incorrect EC2 instance ID', errno.EACCES)

        if await self.middleware.call('user.has_local_administrator_set_up'):
            raise CallError('Local administrator is already set up', errno.EEXIST)

        if username == 'admin':
            if await self.middleware.call('user.query', [['uid', '=', ADMIN_UID]]):
                raise CallError(
                    f'A user with uid={ADMIN_UID} already exists, setting up local administrator is not possible',
                    errno.EEXIST,
                )
            if await self.middleware.call('user.query', [['username', '=', 'admin']]):
                raise CallError('"admin" user already exists, setting up local administrator is not possible',
                                errno.EEXIST)

            if await self.middleware.call('group.query', [['gid', '=', ADMIN_GID]]):
                raise CallError(
                    f'A group with gid={ADMIN_GID} already exists, setting up local administrator is not possible',
                    errno.EEXIST,
                )
            if await self.middleware.call('group.query', [['group', '=', 'admin']]):
                raise CallError('"admin" group already exists, setting up local administrator is not possible',
                                errno.EEXIST)

        await run('truenas-set-authentication-method.py', check=True, encoding='utf-8', errors='ignore',
                  input=json.dumps({'username': username, 'password': password}))
        await self.middleware.call('failover.datastore.force_send')
        await self.middleware.call('etc.generate', 'user')

    @private
    @job(lock=lambda args: f'copy_home_to_{args[1]}')
    async def do_home_copy(self, job, home_old, home_new, username, new_mode, uid):
        if home_old in DEFAULT_HOME_PATHS:
            return

        if new_mode is not None:
            perm_job = await self.middleware.call('filesystem.setperm', {
                'uid': uid,
                'path': home_new,
                'mode': new_mode,
                'options': {'stripacl': True},
            })
        else:
            current_mode = stat.S_IMODE((await self.middleware.call('filesystem.stat', home_old))['mode'])
            perm_job = await self.middleware.call('filesystem.setperm', {
                'uid': uid,
                'path': home_new,
                'mode': f'{current_mode:03o}',
                'options': {'stripacl': True},
            })

        await perm_job.wait()

        command = f"/bin/cp -a {shlex.quote(home_old) + '/' + '.'} {shlex.quote(home_new + '/')}"
        do_copy = await run(["/usr/bin/su", "-", username, "-c", command], check=False)
        if do_copy.returncode != 0:
            raise CallError(f"Failed to copy homedir [{home_old}] to [{home_new}]: {do_copy.stderr.decode()}")

    @private
    async def common_validation(self, verrors, data, schema, group_ids, old=None):
        exclude_filter = [('id', '!=', old['id'])] if old else []
        combined = data if not old else old | data

        users = await self.middleware.call(
            'datastore.query',
            'account.bsdusers',
            exclude_filter,
            {'prefix': 'bsdusr_'}
        )

        if data.get('uid') is not None:
            try:
                existing_user = await self.middleware.call(
                    'user.get_user_obj',
                    {'uid': data['uid']},
                )
            except KeyError:
                pass
            else:
                verrors.add(
                    f'{schema}.uid',
                    f'Uid {data["uid"]} is already used (user {existing_user["pw_name"]} has it)',
                    errno.EEXIST,
                )

        if 'username' in data:
            pw_checkname(verrors, f'{schema}.username', data['username'])

            if filter_list(users, [('username', '=', data['username'])]):
                verrors.add(
                    f'{schema}.username',
                    f'The username "{data["username"]}" already exists.',
                    errno.EEXIST
                )

            if data.get('smb'):
                if filter_list(users, [['username', 'C=', data['username']], ['smb', '=', True]]):
                    verrors.add(
                        f'{schema}.smb',
                        f'Username "{data["username"]}" conflicts with existing SMB user. Note that SMB '
                        f'usernames are case-insensitive.',
                        errno.EEXIST,
                    )

        if combined['smb'] and not await self.middleware.call('smb.is_configured'):
            if (await self.middleware.call('systemdataset.sysdataset_path')) is None:
                verrors.add(
                    f'{schema}.smb',
                    'System dataset is not mounted at expected path. This may indicate '
                    'an underlying issue with the pool hosting the system dataset. '
                    'SMB users may not be configured until this configuration issue is addressed.'
                )
            else:
                verrors.add(
                    f'{schema}.smb',
                    'SMB users may not be configured while SMB service backend is unitialized.'
                )

        if combined['smb'] and combined['password_disabled']:
            verrors.add(
                f'{schema}.password_disabled', 'Password authentication may not be disabled for SMB users.'
            )

        password = data.get('password')
        if not old and not password and not data.get('password_disabled'):
            verrors.add(f'{schema}.password', 'Password is required')
        elif data.get('password_disabled') and password:
            verrors.add(
                f'{schema}.password_disabled',
                'Leave "Password" blank when "Disable password login" is checked.'
            )

        if 'home' in data:
            if await self.middleware.run_in_thread(self.validate_homedir_path, verrors, schema, data, users):
                await check_path_resides_within_volume(verrors, self.middleware, schema, data['home'])

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

        if 'full_name' in data and '\n' in data['full_name']:
            verrors.add(
                f'{schema}.full_name',
                'The "\\n" character is not allowed in a "Full Name".'
            )

        if 'shell' in data and data['shell'] not in await self.middleware.call('user.shell_choices', group_ids):
            verrors.add(
                f'{schema}.shell', 'Please select a valid shell.'
            )

        if 'sudo_commands' in data:
            verrors.add_child(
                f'{schema}.sudo_commands',
                await self.middleware.run_in_thread(validate_sudo_commands, data['sudo_commands']),
            )

        if 'sudo_commands_nopasswd' in data:
            verrors.add_child(
                f'{schema}.sudo_commands_nopasswd',
                await self.middleware.run_in_thread(validate_sudo_commands, data['sudo_commands_nopasswd']),
            )

    def __set_password(self, data):
        if 'password' not in data:
            return
        password = data.pop('password')
        if password:
            data['unixhash'] = crypted_password(password)
            # See http://samba.org.ru/samba/docs/man/manpages/smbpasswd.5.html
            data['smbhash'] = f'{data["username"]}:{data["uid"]}:{"X" * 32}'
            data['smbhash'] += f':{nt_password(password)}:[U         ]:LCT-{int(time.time()):X}:'
        else:
            data['unixhash'] = '*'
            data['smbhash'] = '*'

        return data

    def __set_groups(self, pk, groups):

        groups = set(groups)
        existing_ids = set()
        gms = self.middleware.call_sync(
            'datastore.query', 'account.bsdgroupmembership',
            [('user', '=', pk)], {'prefix': 'bsdgrpmember_'}
        )
        for gm in gms:
            if gm['id'] not in groups:
                self.middleware.call_sync('datastore.delete', 'account.bsdgroupmembership', gm['id'])
            else:
                existing_ids.add(gm['id'])

        for _id in groups - existing_ids:
            group = self.middleware.call_sync(
                'datastore.query', 'account.bsdgroups', [('id', '=', _id)], {'prefix': 'bsdgrp_'}
            )
            if not group:
                raise CallError(f'Group {_id} not found', errno.ENOENT)
            self.middleware.call_sync(
                'datastore.insert',
                'account.bsdgroupmembership',
                {'group': _id, 'user': pk},
                {'prefix': 'bsdgrpmember_'}
            )

    @private
    def update_sshpubkey(self, homedir, user, group):
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
            # Since this is security sensitive, we allow raising exception here
            # if mode fails to be set to 0o700
            self.middleware.call_sync('filesystem.mkdir', {'path': sshpath, 'options': {'mode': '700'}})
        if not os.path.isdir(sshpath):
            raise CallError(f'{sshpath} is not a directory')

        # Make extra sure to enforce correct mode on .ssh directory.
        # stripping the ACL will allow subsequent chmod calls to succeed even if
        # dataset aclmode is restricted.
        try:
            gid = self.middleware.call_sync('group.get_group_obj', {'groupname': group})['gr_gid']
        except Exception:
            # leaving gid at -1 avoids altering the GID value.
            self.logger.debug("Failed to convert %s to gid", group, exc_info=True)

        self.middleware.call_sync('filesystem.setperm', {
            'path': sshpath,
            'mode': str(700),
            'uid': user['uid'],
            'gid': gid,
            'options': {'recursive': True, 'stripacl': True}
        }).wait_sync(raise_error=True)

        with open(keysfile, 'w') as f:
            os.fchmod(f.fileno(), 0o600)
            os.fchown(f.fileno(), user['uid'], gid)
            f.write(f'{pubkey}\n')

    @no_authz_required
    @accepts(Dict(
        'set_password_data',
        Str('username', required=True),
        Password('old_password', default=None),
        Password('new_password', required=True),
    ))
    @pass_app(require=True)
    async def set_password(self, app, data):
        """
        Set the password of the specified `username` to the `new_password`
        specified in payload.

        ValidationErrors will be raised in the following situations:
        * username does not exist
        * account is not local to the NAS (Active Directory, LDAP, etc)
        * account has password authentication disabled
        * account is locked

        NOTE: when authenticated session has less than FULL_ADMIN role,
        password changes will be rejected if the payload does not match the
        currently-authenticated user.

        API keys granting access to this endpoint will be able to reset
        the password of any user.
        """

        verrors = ValidationErrors()
        is_full_admin = credential_has_full_admin(app.authenticated_credentials)
        authenticated_user = None

        if app.authenticated_credentials.is_user_session:
            authenticated_user = app.authenticated_credentials.user['username']

        username = data['username']
        password = data['new_password']

        if not is_full_admin and authenticated_user != username:
            raise CallError(
                f'{username}: currently authenticated credential may not reset '
                'password for this user.',
                errno.EPERM
            )

        entry = await self.middleware.call(
            'user.query',
            [['username', '=', username]],
            {'extra': {'additional_information': ['DS']}}
        )
        if not entry:
            # This only happens if authenticated user has FULL_ADMIN privileges
            # and so we're not concerned about letting admin know that username is
            # bad.
            verrors.add(
                'user.set_password.username',
                f'{username}: user does not exist.'
            )
        else:
            entry = entry[0]
            if not entry['local']:
                # We don't allow resetting passwords on remote directory service.
                verrors.add(
                    'user.set_password.username',
                    f'{username}: user is not local to the TrueNAS server.'
                )

        if data['old_password'] is None and not is_full_admin:
            verrors.add(
                'user.set_password.old_password',
                'FULL_ADMIN role is required in order to bypass check for current password.'
            )

        if data['old_password'] is not None and not await self.middleware.call(
            'auth.libpam_authenticate',
            username, data['old_password']
        ):
            verrors.add(
                'user.set_password.old_password',
                f'{username}: failed to validate password.'
            )

        verrors.check()

        if entry['password_disabled']:
            verrors.add(
                'user.set_password.username',
                f'{username}: password authentication disabled for user'
            )

        if entry['locked']:
            verrors.add(
                'user.set_password.username',
                f'{username}: user account is locked.'
            )

        verrors.check()

        entry = self.__set_password(entry | {'password': password})

        await self.middleware.call('datastore.update', 'account.bsdusers', entry['id'], {
            'bsdusr_unixhash': entry['unixhash'],
            'bsdusr_smbhash': entry['smbhash'],
        })
        await self.middleware.call('etc.generate', 'shadow')

        if entry['smb']:
            passdb_sync = await self.middleware.call('smb.synchronize_passdb')
            await passdb_sync.wait()


class GroupModel(sa.Model):
    __tablename__ = 'account_bsdgroups'

    id = sa.Column(sa.Integer(), primary_key=True)
    bsdgrp_gid = sa.Column(sa.Integer())
    bsdgrp_group = sa.Column(sa.String(120), unique=True)
    bsdgrp_builtin = sa.Column(sa.Boolean(), default=False)
    bsdgrp_sudo_commands = sa.Column(sa.JSON(list))
    bsdgrp_sudo_commands_nopasswd = sa.Column(sa.JSON(list))
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
        datastore_extend_context = 'group.group_extend_context'
        cli_namespace = 'account.group'
        role_prefix = 'ACCOUNT'

    ENTRY = Patch(
        'group_create', 'group_entry',
        ('rm', {'name': 'allow_duplicate_gid'}),
        ('add', Int('id')),
        ('add', Str('group')),
        ('add', Bool('builtin')),
        ('add', Bool('id_type_both')),
        ('add', Bool('local')),
        ('add', Str('nt_name', null=True)),
        ('add', Str('sid', null=True)),
        ('add', List('roles', items=[Str('role')])),
        register=True
    )

    @private
    async def group_extend_context(self, rows, extra):
        mem = {}
        membership = await self.middleware.call(
            'datastore.query', 'account.bsdgroupmembership', [], {'prefix': 'bsdgrpmember_'}
        )
        users = await self.middleware.call('datastore.query', 'account.bsdusers')
        privileges = await self.middleware.call('datastore.query', 'account.privilege')

        # uid and gid variables here reference database ids rather than OS uid / gid
        for g in membership:
            gid = g['group']['id']
            uid = g['user']['id']
            if gid in mem:
                mem[gid].append(uid)
            else:
                mem[gid] = [uid]

        for u in users:
            gid = u['bsdusr_group']['id']
            uid = u['id']
            if gid in mem:
                mem[gid].append(uid)
            else:
                mem[gid] = [uid]

        return {"memberships": mem, "privileges": privileges}

    @private
    async def group_extend(self, group, ctx):
        group['name'] = group['group']
        group['users'] = ctx['memberships'].get(group['id'], [])

        privilege_mappings = privileges_group_mapping(ctx['privileges'], [group['gid']], 'local_groups')
        if privilege_mappings['allowlist']:
            privilege_mappings['roles'].append('HAS_ALLOW_LIST')
            if {'method': '*', 'resource': '*'} in privilege_mappings['allowlist']:
                privilege_mappings['roles'].append('FULL_ADMIN')

        group.update({
            'local': True,
            'id_type_both': False,
            'nt_name': None,
            'sid': None,
            'roles': privilege_mappings['roles']
        })
        return group

    @private
    async def group_compress(self, group):
        to_remove = [
            'name',
            'local',
            'id_type_both',
            'nt_name',
            'sid',
            'roles'
        ]

        for i in to_remove:
            group.pop(i, None)

        return group

    @filterable
    async def query(self, filters, options):
        """
        Query groups with `query-filters` and `query-options`. As a performance optimization, only local groups
        will be queried by default.

        Expanded information may be requested by specifying the extra option `"extra": {"additional_information": []}`.

        The following `additional_information` options are supported:
        `SMB` - include Windows SID and NT Name for group. If this option is not specified, then these
            keys will have `null` value.
        `DS` - include groups from Directory Service (LDAP or Active Directory) in results

        `"extra": {"search_dscache": true}` is a legacy method of querying for directory services groups.
        """
        ds_groups = []
        options = options or {}
        options['extend'] = self._config.datastore_extend
        options['extend_context'] = self._config.datastore_extend_context
        options['prefix'] = self._config.datastore_prefix

        datastore_options = options.copy()
        datastore_options.pop('count', None)
        datastore_options.pop('get', None)
        datastore_options.pop('limit', None)
        datastore_options.pop('offset', None)
        datastore_options.pop('select', None)

        extra = options.get('extra', {})
        dssearch = extra.pop('search_dscache', False)
        additional_information = extra.get('additional_information', [])

        if 'DS' in additional_information:
            dssearch = True
            additional_information.remove('DS')

        if dssearch:
            ds_state = await self.middleware.call('directoryservices.get_state')
            if ds_state['activedirectory'] == 'HEALTHY' or ds_state['ldap'] == 'HEALTHY':
                ds_groups = await self.middleware.call('directoryservices.cache.query', 'GROUPS', filters, options)

        if 'SMB' in additional_information:
            try:
                smb_groupmap = await self.middleware.call("smb.groupmap_list")
            except Exception:
                # If system dataset has failed to properly initialize / is broken
                # then looking up groupmaps will fail.
                self.logger.error('Failed to retrieve SMB groupmap.', exc_info=True)
                smb_groupmap = {
                    'local': {},
                    'local_builtins': {}
                }

        result = await self.middleware.call(
            'datastore.query', self._config.datastore, [], datastore_options
        )

        if 'SMB' in additional_information:
            for entry in result:
                smb_data = smb_groupmap['local'].get(entry['gid'])
                if not smb_data:
                    smb_data = smb_groupmap['local_builtins'].get(entry['gid'], {'nt_name': '', 'sid': ''})

                entry.update({
                    'nt_name': smb_data['nt_name'],
                    'sid': smb_data['sid'],
                })

        return await self.middleware.run_in_thread(
            filter_list, result + ds_groups, filters, options
        )

    @accepts(Dict(
        'group_create',
        Int('gid', validators=[Range(0, TRUENAS_IDMAP_DEFAULT_LOW - 1)]),
        Str('name', required=True),
        Bool('smb', default=True),
        List('sudo_commands', items=[Str('command', empty=False)]),
        List('sudo_commands_nopasswd', items=[Str('command', empty=False)]),
        Bool('allow_duplicate_gid', default=False),
        List('users', items=[Int('id')], required=False),
        register=True,
    ), audit='Create group', audit_extended=lambda data: data['name'])
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

        if data.get('gid') is None:
            data['gid'] = await self.get_next_gid()

        group = data.copy()
        group['group'] = group.pop('name')

        users = group.pop('users', [])

        group = await self.group_compress(group)
        pk = await self.middleware.call('datastore.insert', 'account.bsdgroups', group, {'prefix': 'bsdgrp_'})

        for user in users:
            await self.middleware.call(
                'datastore.insert', 'account.bsdgroupmembership', {'bsdgrpmember_group': pk, 'bsdgrpmember_user': user}
            )

        if reload_users:
            await self.middleware.call('service.reload', 'user')

        if data['smb']:
            gm_job = await self.middleware.call('smb.synchronize_group_mappings')
            await gm_job.wait()

        return pk

    @accepts(
        Int('id'),
        Patch(
            'group_create',
            'group_update',
            ('attr', {'update': True}),
        ),
        audit='Update group',
        audit_callback=True,
    )
    @returns(Int('primary_key'))
    async def do_update(self, audit_callback, pk, data):
        """
        Update attributes of an existing group.
        """

        group = await self.get_instance(pk)
        audit_callback(group['name'])

        groupmap_changed = False

        if data.get('gid') == group['gid']:
            data.pop('gid')  # Only check for duplicate GID if we are updating it

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
            primary_users = {
                u['id']
                for u in await self.middleware.call(
                    'datastore.query',
                    'account.bsdusers',
                    [('bsdusr_group', '=', pk)],
                )
            }
            existing = {
                i['bsdgrpmember_user']['id']: i
                for i in await self.middleware.call(
                    'datastore.query',
                    'account.bsdgroupmembership',
                    [('bsdgrpmember_group', '=', pk)]
                )
            }
            to_remove = set(existing.keys()) - set(data['users'])
            for i in to_remove:
                await self.middleware.call('datastore.delete', 'account.bsdgroupmembership', existing[i]['id'])

            to_add = set(data['users']) - set(existing.keys()) - primary_users
            for i in to_add:
                await self.middleware.call(
                    'datastore.insert',
                    'account.bsdgroupmembership',
                    {'bsdgrpmember_group': pk, 'bsdgrpmember_user': i},
                )

        await self.middleware.call('service.reload', 'user')

        if groupmap_changed:
            gm_job = await self.middleware.call('smb.synchronize_group_mappings')
            await gm_job.wait()

        return pk

    @accepts(Int('id'), Dict('options', Bool('delete_users', default=False)), audit='Delete group', audit_callback=True)
    @returns(Int('primary_key'))
    async def do_delete(self, audit_callback, pk, options):
        """
        Delete group `id`.

        The `delete_users` option deletes all users that have this group as their primary group.
        """

        group = await self.get_instance(pk)
        audit_callback(group['name'] + (' and all its users' if options['delete_users'] else ''))

        if group['builtin']:
            raise CallError('A built-in group cannot be deleted.', errno.EACCES)

        await self.middleware.call('privilege.before_group_delete', group)

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

        if group['smb']:
            gm_job = await self.middleware.call('smb.synchronize_group_mappings')
            await gm_job.wait()

        await self.middleware.call('service.reload', 'user')
        try:
            await self.middleware.call('idmap.gencache.del_idmap_cache_entry', {
                'entry_type': 'GID2SID',
                'entry': group['gid']
            })
        except MatchNotFound:
            pass

        return pk

    @accepts(roles=['ACCOUNT_READ'])
    @returns(Int('next_available_gid'))
    async def get_next_gid(self):
        """
        Get the next available/free gid.
        """
        used_gids = (
            {
                group['bsdgrp_gid']
                for group in await self.middleware.call('datastore.query', 'account.bsdgroups')
            } |
            set((await self.middleware.call('privilege.used_local_gids')).keys())
        )
        # We should start gid from 3000 to avoid potential conflicts - Reference: NAS-117892
        next_gid = 3000
        while next_gid in used_gids:
            next_gid += 1

        return next_gid

    @accepts(Dict(
        'get_group_obj',
        Str('groupname', default=None),
        Int('gid', default=None),
        Bool('sid_info', default=False)
    ), roles=['ACCOUNT_READ'])
    @returns(Dict(
        'group_info',
        Str('gr_name'),
        Int('gr_gid'),
        List('gr_mem'),
        SID('sid', null=True),
        Str('source', enum=[mod.name for mod in list(NssModule)]),
        Bool('local'),
    ))
    def get_group_obj(self, data):
        """
        Returns dictionary containing information from struct grp for the group specified by either
        the `groupname` or `gid`.

        If `sid_info` is specified then addition SMB / domain information is returned for the
        group.

        Output contains following keys:

        `gr_name` - name of the group

        `gr_gid` - group id of the group

        `gr_mem` - list of gids that are members of the group

        `sid_info` - optional SMB information if `sid_info` is specified specified, otherwise
        this field will be null.

        `local` - boolean indicating whether this group is local to the NAS or provided by a
        directory service.
        """
        verrors = ValidationErrors()
        if not data['groupname'] and data['gid'] is None:
            verrors.add('get_group_obj.groupname', 'Either "groupname" or "gid" must be specified')
        if data['groupname'] and data['gid'] is not None:
            verrors.add('get_group_obj.groupname', '"groupname" and "gid" may not be simultaneously specified')
        verrors.check()

        if data['groupname']:
            grp_obj = grp.getgrnam(data['groupname'], as_dict=True)
        else:
            grp_obj = grp.getgrgid(data['gid'], as_dict=True)

        grp_obj['local'] = grp_obj['source'] == NssModule.FILES.name
        if data['sid_info']:
            match grp_obj['source']:
                case NssModule.FILES.name | NssModule.WINBIND.name:
                    # winbind provides idmapping for local and AD users
                    try:
                        idmap_ctx = idmap_winbind.WBClient()
                    except wbclient.WBCError as e:
                        # Library error from libwbclient.
                        # Don't bother logging if winbind isn't running since
                        # we have plenty of other places that are logging that
                        # error condition
                        if e.error_code != wbclient.WBC_ERR_WINBIND_NOT_AVAILABLE:
                            self.logger.error('Failed to retrieve SID for gid: %d',
                                              grp_obj['gr_gid'], exc_info=True)

                        idmap_ctx = None
                case NssModule.SSS.name:
                    # SSSD provides ID mapping for IPA domains
                    idmap_ctx = idmap_sss.SSSClient()
                case _:
                    # We're not raising an exception here since it
                    # can be a critical areai
                    self.logger.error(
                        '%s: unknown ID source. Please file a bug report.',
                        grp_obj['source']
                    )
                    idmap_ctx = None

            if idmap_ctx is not None:
                try:
                    sid = idmap_ctx.uidgid_to_idmap_entry({
                        'id_type': 'GROUP',
                        'id': grp_obj['gr_gid']
                    })['sid']
                except MatchNotFound:
                    if grp_obj['source'] == NssModule.FILES.name:
                        # Local user that doesn't have groupmap entry
                        # we can simply apply default prefix
                        sid = SID_LOCAL_GROUP_PREFIX + str(grp_obj['gr_gid'])
                    else:
                        sid = None
            else:
                sid = None

            if sid:
                grp_obj['sid_info'] = {
                    'sid': sid
                }
            else:
                grp_obj['sid_info'] = None

        return grp_obj

    async def __common_validation(self, verrors, data, schema, pk=None):

        exclude_filter = [('id', '!=', pk)] if pk else []

        if data.get('smb') and not await self.middleware.call('smb.is_configured'):
            verrors.add(
                f'{schema}.smb', 'SMB groups may not be configured while SMB service backend is unitialized.'
            )

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

                if filter_list(smb_groups, [['group', 'C=', data['name']]]):
                    verrors.add(
                        f'{schema}.name',
                        f'Group name "{data["name"]}" conflicts with existing groupmap entry. '
                        f'SMB group mapping is not permitted for this group. Note that SMB '
                        f'group names are case-insensitive.',
                        errno.EEXIST,
                    )

            existing = await self.middleware.call(
                'datastore.query', 'account.bsdgroups',
                [('group', '=', data['name'])] + exclude_filter, {'prefix': 'bsdgrp_'}
            )
            if existing:
                verrors.add(
                    f'{schema}.name',
                    f'A Group with the name "{data["name"]}" already exists.',
                    errno.EEXIST,
                )

            pw_checkname(verrors, f'{schema}.name', data['name'])

        allow_duplicate_gid = data.pop('allow_duplicate_gid', False)
        if data.get('gid') and not allow_duplicate_gid:
            try:
                existing = await self.middleware.call(
                    'group.get_group_obj', {'gid': data['gid']},
                )
            except KeyError:
                pass
            else:
                verrors.add(
                    f'{schema}.gid',
                    f'Gid {data["gid"]} is already used (group {existing["gr_name"]} has it)',
                    errno.EEXIST,
                )

        if data.get('gid'):
            if privilege := (await self.middleware.call('privilege.used_local_gids')).get(data['gid']):
                verrors.add(
                    f'{schema}.gid',
                    f'A privilege {privilege["name"]!r} already uses this group ID.',
                    errno.EINVAL,
                )

        if 'users' in data:
            existing = {
                i['id']
                for i in await self.middleware.call(
                    'datastore.query',
                    'account.bsdusers',
                    [('id', 'in', data['users'])],
                )
            }
            notfound = set(data['users']) - existing
            if notfound:
                verrors.add(
                    f'{schema}.users',
                    f'Following users do not exist: {", ".join(map(str, notfound))}',
                )

            primary_users = await self.middleware.call(
                'datastore.query',
                'account.bsdusers',
                [('bsdusr_group', '=', pk)],
            )
            notfound = []
            for user in primary_users:
                if user['id'] not in data['users']:
                    notfound.append(user['bsdusr_username'])
            if notfound:
                verrors.add(
                    f'{schema}.users',
                    f'This group is primary for the following users: {", ".join(map(str, notfound))}. '
                    'You can\'t remove them.',
                )

        if 'sudo_commands' in data:
            verrors.add_child(
                f'{schema}.sudo_commands',
                await self.middleware.run_in_thread(validate_sudo_commands, data['sudo_commands']),
            )

        if 'sudo_commands_nopasswd' in data:
            verrors.add_child(
                f'{schema}.sudo_commands_nopasswd',
                await self.middleware.run_in_thread(validate_sudo_commands, data['sudo_commands_nopasswd']),
            )


async def setup(middleware):
    if await middleware.call('keyvalue.get', 'run_migration', False):
        await middleware.call('user.sync_builtin')
