import errno
import glob
import json
import os
import pam
import shlex
import shutil
import stat
import wbclient
from pathlib import Path
from collections import defaultdict
from contextlib import suppress

from sqlalchemy.orm import relationship

from dataclasses import asdict
from middlewared.api import api_method
from middlewared.api.current import (
    GroupEntry,
    GroupCreateArgs,
    GroupCreateResult,
    GroupDeleteArgs,
    GroupDeleteResult,
    GroupGetGroupObjArgs,
    GroupGetGroupObjResult,
    GroupGetNextGidArgs,
    GroupGetNextGidResult,
    GroupUpdateArgs,
    GroupUpdateResult,
    UserEntry,
    UserCreateArgs,
    UserCreateResult,
    UserDeleteArgs,
    UserDeleteResult,
    UserGetNextUidArgs,
    UserGetNextUidResult,
    UserGetUserObjArgs,
    UserGetUserObjResult,
    UserHasLocalAdministratorSetUpArgs,
    UserHasLocalAdministratorSetUpResult,
    UserSetupLocalAdministratorArgs,
    UserSetupLocalAdministratorResult,
    UserSetPasswordArgs,
    UserSetPasswordResult,
    UserShellChoicesArgs,
    UserShellChoicesResult,
    UserUpdateArgs,
    UserUpdateResult,
)
from middlewared.service import CallError, CRUDService, ValidationErrors, pass_app, private, job
from middlewared.service_exception import MatchNotFound
import middlewared.sqlalchemy as sa
from middlewared.utils import run, filter_list
from middlewared.utils.crypto import generate_nt_hash, sha512_crypt, generate_string
from middlewared.utils.directoryservices.constants import DSType, DSStatus
from middlewared.utils.filesystem.copy import copytree, CopyTreeConfig
from middlewared.utils.nss import pwd, grp
from middlewared.utils.nss.nss_common import NssModule
from middlewared.utils.privilege import credential_has_full_admin, privileges_group_mapping
from middlewared.async_validators import check_path_resides_within_volume
from middlewared.utils.sid import db_id_to_rid, DomainRid
from middlewared.plugins.account_.constants import (
    ADMIN_UID, ADMIN_GID, SKEL_PATH, DEFAULT_HOME_PATH, DEFAULT_HOME_PATHS,
    USERNS_IDMAP_DIRECT, USERNS_IDMAP_NONE, ALLOWED_BUILTIN_GIDS,
)
from middlewared.plugins.smb_.constants import SMBBuiltin
from middlewared.plugins.idmap_.idmap_constants import (
    BASE_SYNTHETIC_DATASTORE_ID,
    IDType,
)
from middlewared.plugins.idmap_ import idmap_winbind
from middlewared.plugins.idmap_ import idmap_sss


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
    return generate_nt_hash(cleartext)


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


def filters_include_ds_accounts(filters):
    """ Check for filters limiting to local accounts """
    for f in filters:
        if len(f) < 3:
            # OR -- assume evaluation for this will result in including DS
            continue

        # Directory services do not provide builtin accounts
        # local explicitly denotes not directory service
        if f[0] in ('local', 'builtin'):
            match f[1]:
                case '=':
                    if f[2] is True:
                        return False
                case '!=':
                    if f[2] is False:
                        return False

                case _:
                    pass

    return True


class GroupMembershipModel(sa.Model):
    __tablename__ = 'account_bsdgroupmembership'

    id = sa.Column(sa.Integer(), primary_key=True)
    bsdgrpmember_group_id = sa.Column(sa.Integer(), sa.ForeignKey("account_bsdgroups.id", ondelete="CASCADE"))
    bsdgrpmember_user_id = sa.Column(sa.Integer(), sa.ForeignKey("account_bsdusers.id", ondelete="CASCADE"))


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
    bsdusr_userns_idmap = sa.Column(sa.Integer(), default=USERNS_IDMAP_NONE)
    bsdusr_password_disabled = sa.Column(sa.Boolean(), default=False)
    bsdusr_ssh_password_enabled = sa.Column(sa.Boolean(), default=False)
    bsdusr_locked = sa.Column(sa.Boolean(), default=False)
    bsdusr_sudo_commands = sa.Column(sa.JSON(list))
    bsdusr_sudo_commands_nopasswd = sa.Column(sa.JSON(list))
    bsdusr_group_id = sa.Column(sa.ForeignKey('account_bsdgroups.id'), index=True)
    bsdusr_email = sa.Column(sa.String(254), nullable=True)
    bsdusr_groups = relationship('GroupModel', secondary=lambda: GroupMembershipModel.__table__)


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
        entry = UserEntry

    @private
    async def user_extend_context(self, rows, extra):
        group_roles = await self.middleware.call('group.query', [['local', '=', True]], {'select': ['id', 'roles']})

        user_api_keys = defaultdict(list)
        for key in await self.middleware.call('api_key.query'):
            if not key['local']:
                continue

            user_api_keys[key['username']].append(key['id'])

        return {
            'stig_enabled': (await self.middleware.call('system.security.config'))['enable_gpos_stig'],
            'server_sid': await self.middleware.call('smb.local_server_sid'),
            'user_2fa_mapping': ({
                entry['user']['id']: bool(entry['secret']) for entry in await self.middleware.call(
                    'datastore.query', 'account.twofactor_user_auth', [['user_id', '!=', None]]
                )
            }),
            'user_api_keys': user_api_keys,
            'roles_mapping': {i['id']: i['roles'] for i in group_roles}
        }

    @private
    def _read_authorized_keys(self, homedir):
        with suppress(FileNotFoundError):
            with open(f'{homedir}/.ssh/authorized_keys') as f:
                try:
                    return f.read().strip()
                except UnicodeDecodeError:
                    self.logger.warning('Invalid encoding detected in authorized_keys file')

    @private
    async def user_extend(self, user, ctx):
        user['groups'] = [g['id'] for g in user['groups']]

        # Normalize email, empty is really null
        if user['email'] == '':
            user['email'] = None

        # Get authorized keys
        user['sshpubkey'] = await self.middleware.run_in_thread(self._read_authorized_keys, user['home'])

        user['immutable'] = user['builtin'] or (user['uid'] == ADMIN_UID)
        user['twofactor_auth_configured'] = bool(ctx['user_2fa_mapping'][user['id']])

        if user['userns_idmap'] == USERNS_IDMAP_DIRECT:
            user['userns_idmap'] = 'DIRECT'
        elif user['userns_idmap'] == USERNS_IDMAP_NONE:
            user['userns_idmap'] = None

        user_roles = set()
        for g in user['groups'] + [user['group']['id']]:
            if not (entry := ctx['roles_mapping'].get(g)):
                continue

            user_roles |= set(entry)

        if user['smb']:
            sid = f'{ctx["server_sid"]}-{db_id_to_rid(IDType.USER, user["id"])}'
        else:
            sid = None

        user.update({
            'local': True,
            'id_type_both': False,
            'sid': sid,
            'roles': list(user_roles),
            'api_keys': ctx['user_api_keys'][user['username']]
        })
        if ctx['stig_enabled']:
            # NTLM authentication relies on non-FIPS crypto
            user.update({
                'smb': False,
                'sid': None,
                'smbhash': '*'
            })

        return user

    @private
    def user_compress(self, user):
        to_remove = [
            'api_keys',
            'local',
            'id_type_both',
            'sid',
            'immutable',
            'home_create',
            'roles',
            'random_password',
            'twofactor_auth_configured',
        ]

        match user['userns_idmap']:
            case 'DIRECT':
                user['userns_idmap'] = USERNS_IDMAP_DIRECT
            case None:
                user['userns_idmap'] = USERNS_IDMAP_NONE
            case _:
                pass

        for i in to_remove:
            user.pop(i, None)

        return user

    async def query(self, filters, options):
        """
        Query users with `query-filters` and `query-options`.

        If users provided by Active Directory or LDAP are not desired, then
        "local", "=", True should be added to filters.
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

        if filters_include_ds_accounts(filters):
            ds = await self.middleware.call('directoryservices.status')
            if ds['type'] is not None and ds['status'] == DSStatus.HEALTHY.name:
                ds_users = await self.middleware.call(
                    'directoryservices.cache.query', 'USER', filters, options.copy()
                )

                match DSType(ds['type']):
                    case DSType.AD:
                        # For AD users, we will not have 2FA attribute normalized so let's do that
                        ad_users_2fa_mapping = await self.middleware.call('auth.twofactor.get_ad_users')
                        for index, user in enumerate(filter(
                            lambda u: not u['local'] and 'twofactor_auth_configured' not in u, ds_users)
                        ):
                            ds_users[index]['twofactor_auth_configured'] = bool(ad_users_2fa_mapping.get(user['sid']))
                    case _:
                        # FIXME - map twofactor_auth_configured hint for LDAP users
                        pass

        result = await self.middleware.call(
            'datastore.query', self._config.datastore, [], datastore_options
        )

        return await self.middleware.run_in_thread(
            filter_list, result + ds_users, filters, options
        )

    @private
    def validate_homedir_mountinfo(self, verrors, schema, home_path):
        sfs = self.middleware.call_sync('filesystem.statfs', home_path.as_posix())
        if 'RO' in sfs['flags']:
            verrors.add(f'{schema}.home', 'Path has the ZFS readonly property set.')
            return False

        if sfs['fstype'] != 'zfs':
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
                self.validate_homedir_mountinfo(verrors, schema, p.parent)

        elif self.validate_homedir_mountinfo(verrors, schema, p):
            attrs = self.middleware.call_sync('filesystem.stat', data['home'])['attributes']
            if 'IMMUTABLE' in attrs:
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

    @api_method(UserCreateArgs, UserCreateResult, audit='Create user', audit_extended=lambda data: data['username'])
    def do_create(self, data):
        """
        Create a new user.
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

        create = data.pop('group_create')
        group_created = False

        if create:
            group = self.middleware.call_sync('group.query', [
                ('group', '=', data['username']),
                ('local', '=', True)
            ])
            if group:
                group = group[0]
            else:
                group = self.middleware.call_sync('group.create_internal', {
                    'name': data['username'],
                    'smb': False,
                    'sudo_commands': [],
                    'sudo_commands_nopasswd': [],
                }, False)
                group = self.middleware.call_sync('group.query', [
                    ('id', '=', group), ('local', '=', True)
                ])[0]
                group_created = True

            data['group'] = group['id']
        else:
            group = self.middleware.call_sync('group.query', [('id', '=', data['group'])])
            if not group:
                raise CallError(f'Group {data["group"]} not found')
            group = group[0]

        if data['smb']:
            data['groups'].append((self.middleware.call_sync(
                'group.query', [('group', '=', 'builtin_users'), ('local', '=', True)], {'get': True},
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
        password = data['password']
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
            self.middleware.call_sync('smb.update_passdb_user', data | {'id': pk})

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
                self.logger.warning('Failed to update authorized keys', exc_info=True)
                raise CallError(f'Failed to update authorized keys: {e}')

        return self.middleware.call_sync('user.query', [['id', '=', pk]], {'get': True}) | {'password': password}

    @api_method(UserUpdateArgs, UserUpdateResult, audit='Update user', audit_callback=True)
    @pass_app()
    def do_update(self, app, audit_callback, pk, data):
        """
        Update attributes of an existing user.
        """

        if pk > BASE_SYNTHETIC_DATASTORE_ID:
            # datastore ids for directory services are created by adding the
            # posix ID to a base value so that we can use getpwuid / getgrgid to
            # convert back to a username / group name
            try:
                username = self.middleware.call_sync(
                    'user.get_user_obj', {'uid': pk - BASE_SYNTHETIC_DATASTORE_ID}
                )['pw_name']
            except KeyError:
                username = 'UNKNOWN'

            audit_callback(username)
            raise CallError(
                'Users provided by a directory service must be modified through the identity provider '
                '(LDAP server or domain controller).', errno.EPERM
            )

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
                user['uid'] in [0, ADMIN_UID] or
                self.middleware.call_sync('filesystem.is_dataset_path', home)
            ):
                verrors.add('user_update.sshpubkey', 'Home directory is not writable, leave this blank"')

        # Do not allow attributes to be changed for builtin user
        if user['immutable']:
            if 'home_mode' in data:
                verrors.add('user_update.home_mode', 'This attribute cannot be changed')

            for i in ('group', 'home', 'username', 'smb', 'userns_idmap'):
                if i in data and data[i] != user[i]:
                    verrors.add(f'user_update.{i}', 'This attribute cannot be changed')

        if not user['smb'] and data.get('smb') and not data.get('password'):
            # Changing from non-smb user to smb user requires re-entering password.
            verrors.add('user_update.smb',
                        'Password must be reset in order to enable SMB authentication')

        verrors.check()

        must_change_pdb_entry = False
        for k in ('username', 'password', 'locked'):
            new_val = data.get(k)
            old_val = user.get(k)
            if new_val is not None and old_val != new_val:
                if k == 'username':
                    try:
                        self.middleware.call_sync("smb.remove_passdb_user", old_val, user['sid'])
                    except Exception:
                        self.logger.debug("Failed to remove passdb entry for user [%s]",
                                          old_val, exc_info=True)

                must_change_pdb_entry = True

        if user['smb'] is True and data.get('smb') is False:
            try:
                must_change_pdb_entry = False
                self.middleware.call_sync("smb.remove_passdb_user", user['username'], user['sid'])
            except Exception:
                self.logger.debug("Failed to remove passdb entry for user [%s]",
                                  user['username'], exc_info=True)

        if user['smb'] is False and data.get('smb') is True:
            must_change_pdb_entry = True

        # Copy the home directory if it changed
        home_copy = False
        home_old = None
        if has_home and 'home' in data:
            if data.get('home_create', False):
                data['home'] = os.path.join(data['home'], data.get('username') or user['username'])

            if had_home and user['home'] != data['home']:
                home_copy = True
                home_old = user['home']

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
            self.logger.warning('Failed to update authorized keys', exc_info=True)
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
        password = user.get('password')

        self.__set_password(user)

        user = self.user_compress(user)
        self.middleware.call_sync('datastore.update', 'account.bsdusers', pk, user, {'prefix': 'bsdusr_'})

        self.middleware.call_sync('service.reload', 'ssh')
        self.middleware.call_sync('service.reload', 'user')
        if user['smb'] and must_change_pdb_entry:
            self.middleware.call_sync('smb.update_passdb_user', user)

        return self.middleware.call_sync('user.query', [['id', '=', pk]], {'get': True}) | {'password': password}

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

    @api_method(UserDeleteArgs, UserDeleteResult, audit='Delete user', audit_callback=True)
    @pass_app(rest=True)
    def do_delete(self, app, audit_callback, pk, options):
        """
        Delete user `id`.

        The `delete_group` option deletes the user primary group if it is not being used by
        any other user.
        """
        if pk > BASE_SYNTHETIC_DATASTORE_ID:
            # datastore ids for directory services are created by adding the
            # posix ID to a base value so that we can use getpwuid / getgrgid to
            # convert back to a username / group name
            try:
                username = self.middleware.call_sync(
                    'user.get_user_obj', {'uid': pk - BASE_SYNTHETIC_DATASTORE_ID}
                )['pw_name']
            except KeyError:
                username = 'UNKNOWN'

            audit_callback(username)
            raise CallError(
                'Users provided by a directory service must be deleted from the identity provider '
                '(LDAP server or domain controller).', errno.EPERM
            )

        user = self.middleware.call_sync('user.get_instance', pk)
        audit_callback(user['username'])

        if (
            app and
            app.authenticated_credentials.is_user_session and
            user['username'] == app.authenticated_credentials.user['username']
        ):
            raise CallError('Cannot delete the currently active user', errno.EINVAL)

        if user['builtin']:
            raise CallError('Cannot delete a built-in user', errno.EINVAL)

        if user['immutable']:
            raise CallError('Cannot delete an immutable user', errno.EINVAL)

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
                    self.logger.warning(f'Failed to delete primary group of {user["username"]}', exc_info=True)

        if user['home'] and user['home'] not in DEFAULT_HOME_PATHS:
            try:
                shutil.rmtree(os.path.join(user['home'], '.ssh'))
            except Exception:
                pass

        if user['smb']:
            self.middleware.call_sync('smb.remove_passdb_user', user['username'], user['sid'])

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

    @api_method(UserShellChoicesArgs, UserShellChoicesResult)
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

    @api_method(UserGetUserObjArgs, UserGetUserObjResult, roles=['ACCOUNT_READ'])
    def get_user_obj(self, data):
        """
        Returns dictionary containing information from struct passwd for the user specified by either
        the username or uid. Bypasses user cache.

        NOTE: results will not include nested groups for Active Directory users.
        """
        verrors = ValidationErrors()
        if not data['username'] and data['uid'] is None:
            verrors.add('get_user_obj.username', 'Either "username" or "uid" must be specified.')

        if data['username'] and data['uid'] is not None:
            verrors.add('get_user_obj.username', '"username" and "uid" may not be simultaneously specified')
        verrors.check()

        # NOTE: per request from UI team we are overriding default library
        # KeyError message with a clearer one
        #
        # Many callers to user.get_user_obj may be catching KeyError and so
        # changing exception type is something that should be approached
        # carefully.
        if data['username']:
            try:
                user_obj = pwd.getpwnam(data['username'], as_dict=True)
            except KeyError:
                raise KeyError(f'{data["username"]}: user with this name does not exist') from None
        else:
            try:
                user_obj = pwd.getpwuid(data['uid'], as_dict=True)
            except KeyError:
                raise KeyError(f'{data["uid"]}: user with this id does not exist') from None

        match user_obj['source']:
            case NssModule.FILES.name:
                user_obj['source'] = 'LOCAL'
            case NssModule.WINBIND.name:
                user_obj['source'] = 'ACTIVEDIRECTORY'
            case NssModule.SSS.name:
                user_obj['source'] = 'LDAP'
            case _:
                self.logger.error('%s: unknown ID source.', user_obj['source'])
                raise ValueError(f'{user_obj["source"]}: unknown ID source. Please file a bug report.')

        user_obj['local'] = user_obj['source'] == 'LOCAL'

        if data['get_groups']:
            user_obj['grouplist'] = os.getgrouplist(user_obj['pw_name'], user_obj['pw_gid'])
        else:
            user_obj['grouplist'] = None

        if data['sid_info']:
            sid = None
            match user_obj['source']:
                case 'LOCAL':
                    idmap_ctx = None
                    db_entry = self.middleware.call_sync('user.query', [
                        ['username', '=', user_obj['pw_name']],
                        ['local', '=', True]
                    ], {'select': ['sid']})
                    if not db_entry:
                        self.logger.error(
                            '%s: local user exists on server but does not exist in the '
                            'the user account table.', user_obj['pw_name']
                        )
                    else:
                        sid = db_entry[0]['sid']
                case 'ACTIVEDIRECTORY':
                    # winbind provides idmapping for AD users
                    try:
                        idmap_ctx = idmap_winbind.WBClient()
                    except wbclient.WBCError as e:
                        if e.error_code != wbclient.WBC_ERR_WINBIND_NOT_AVAILABLE:
                            self.logger.error('Failed to retrieve SID for uid: %d',
                                              user_obj['pw_uid'], exc_info=True)

                        idmap_ctx = None
                case 'LDAP':
                    # SSSD provides ID mapping for IPA domains
                    idmap_ctx = idmap_sss.SSSClient()
                case _:
                    self.logger.error('%s: unknown ID source.', user_obj['source'])
                    raise ValueError(f'{user_obj["source"]}: unknown ID source. Please file a bug report.')

            if idmap_ctx is not None:
                try:
                    sid = idmap_ctx.uidgid_to_idmap_entry({
                        'id_type': 'USER',
                        'id': user_obj['pw_uid']
                    })['sid']
                except MatchNotFound:
                    # This is a more odd situation. Most likely case is that the user account exists
                    # in IPA but doesn't have a SID assigned to it. All AD users have SIDs.
                    sid = None

            user_obj['sid'] = sid
        else:
            user_obj['sid'] = None

        return user_obj

    @api_method(UserGetNextUidArgs, UserGetNextUidResult, roles=['ACCOUNT_READ'])
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

    @api_method(
        UserHasLocalAdministratorSetUpArgs, UserHasLocalAdministratorSetUpResult,
        authentication_required=False
    )
    async def has_local_administrator_set_up(self):
        """
        Return whether a local administrator with a valid password exists.

        This is used when the system is installed without a password and must be set on
        first use/login.
        """
        return len(await self.middleware.call('privilege.local_administrators')) > 0

    @api_method(
        UserSetupLocalAdministratorArgs, UserSetupLocalAdministratorResult,
        audit='Set up local administrator',
        authentication_required=False
    )
    @pass_app()
    async def setup_local_administrator(self, app, username, password, options):
        """
        Set up local administrator (this method does not require authentication if local administrator is not already
        set up).
        """
        if await self.middleware.call('user.has_local_administrator_set_up'):
            raise CallError('Local administrator is already set up', errno.EEXIST)

        if username == 'truenas_admin':
            # first check based on NSS to catch collisions with AD / LDAP users
            try:
                pwd_obj = await self.middleware.call('user.get_user_obj', {'uid': ADMIN_UID})
                raise CallError(
                    f'A {pwd_obj["source"].lower()} user with uid={ADMIN_UID} already exists, '
                    'setting up local administrator is not possible',
                    errno.EEXIST,
                )
            except KeyError:
                pass

            try:
                pwd_obj = await self.middleware.call('user.get_user_obj', {'username': username})
                raise CallError(f'{username!r} {pwd_obj["source"].lower()} user already exists, '
                                'setting up local administrator is not possible',
                                errno.EEXIST)
            except KeyError:
                pass

            try:
                grp_obj = await self.middleware.call('group.get_group_obj', {'gid': ADMIN_GID})
                raise CallError(
                    f'A {grp_obj["source"].lower()} group with gid={ADMIN_GID} already exists, '
                    'setting up local administrator is not possible',
                    errno.EEXIST,
                )
            except KeyError:
                pass

            try:
                grp_obj = await self.middleware.call('group.get_group_obj', {'groupname': username})
                raise CallError(f'{username!r} {grp_obj["source"].lower()} group already exists, '
                                'setting up local administrator is not possible',
                                errno.EEXIST)
            except KeyError:
                pass

            # double-check our database in case we have for some reason failed to write to passwd
            local_users = await self.middleware.call('user.query', [['local', '=', True]])
            local_groups = await self.middleware.call('group.query', [['local', '=', True]])

            if filter_list(local_users, [['uid', '=', ADMIN_UID]]):
                raise CallError(
                    f'A user with uid={ADMIN_UID} already exists, setting up local administrator is not possible',
                    errno.EEXIST,
                )

            if filter_list(local_users, [['username', '=', username]]):
                raise CallError(f'{username!r} user already exists, setting up local administrator is not possible',
                                errno.EEXIST)

            if filter_list(local_groups, [['gid', '=', ADMIN_GID]]):
                raise CallError(
                    f'A group with gid={ADMIN_GID} already exists, setting up local administrator is not possible',
                    errno.EEXIST,
                )

            if filter_list(local_groups, [['group', '=', username]]):
                raise CallError(f'{username!r} group already exists, setting up local administrator is not possible',
                                errno.EEXIST)

        await run('truenas-set-authentication-method.py', check=True, encoding='utf-8', errors='ignore',
                  input=json.dumps({'username': username, 'password': password}))
        await self.middleware.call('failover.datastore.force_send')
        await self.middleware.call('etc.generate', 'user')

    @private
    @job(lock=lambda args: f'copy_home_to_{args[1]}')
    def do_home_copy(self, job, home_old, home_new, username, new_mode, uid):
        if home_old in DEFAULT_HOME_PATH:
            return

        # We need to set permission and strip ACL first before copying files
        if new_mode is not None:
            perm_job = self.middleware.call_sync('filesystem.setperm', {
                'uid': uid,
                'path': home_new,
                'mode': new_mode,
                'options': {'stripacl': True},
            })
        else:
            current_mode = stat.S_IMODE(self.middleware.call_sync('filesystem.stat', home_old)['mode'])
            perm_job = self.middleware.call_sync('filesystem.setperm', {
                'uid': uid,
                'path': home_new,
                'mode': f'{current_mode:03o}',
                'options': {'stripacl': True},
            })

        perm_job.wait_sync()

        return asdict(copytree(home_old, home_new, CopyTreeConfig(exist_ok=True, job=job)))

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

        if data.get('userns_idmap'):
            if await self.middleware.call('group.query', [
                ['local', '=', True],
                ['roles', '!=', []],
                ['id', 'in', group_ids],
            ]):
                verrors.add(
                    f'{schema}.userns_idmap',
                    'User namespace idmaps may not be configured for privileged accounts.'
                )

        if data.get('random_password') and data.get('password'):
            verrors.add(
                f'{schema}.random_password',
                'Requesting a randomized password while simultaneously supplying '
                'an explicit password is not permitted.'
            )
        elif data.get('random_password'):
            data['password'] = generate_string(string_size=20)

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

        if combined['smb'] and (await self.middleware.call('system.security.config'))['enable_gpos_stig']:
            verrors.add(
                f'{schema}.smb',
                'SMB authentication for local user accounts is not permitted when General Purpose OS '
                'STIG compatibility is enabled.'
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

            existing_groups = {g['id']: g for g in await self.middleware.call('datastore.query', 'account_bsdgroups')}

            for idx, dbid in enumerate(data.get('groups') or []):
                if dbid not in existing_groups:
                    verrors.add(
                        f'{schema}.groups.{idx}',
                        'This group does not exist.'
                    )

                if dbid >= BASE_SYNTHETIC_DATASTORE_ID:
                    verrors.add(
                        f'{schema}.groups.{idx}',
                        'Local users may not be members of directory services groups.'
                    )

                entry = existing_groups.get(dbid)
                if entry and entry['bsdgrp_builtin'] and entry['bsdgrp_gid'] not in ALLOWED_BUILTIN_GIDS:
                    verrors.add(
                        f'{schema}.groups.{idx}',
                        f'{entry["bsdgrp_group"]}: membership of this builtin group may not be altered.'
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

        two_factor_config = await self.middleware.call('auth.twofactor.config')
        if (
            data.get(
                'ssh_password_enabled', False
            ) and two_factor_config['enabled'] and two_factor_config['services']['ssh']
        ):
            error = [
                f'{schema}.ssh_password_enabled',
                '2FA for this user needs to be explicitly configured before password based SSH access is enabled.'
            ]
            if old is None:
                error[1] += (' User will be created with SSH password access disabled and after 2FA has been '
                             'configured for this user, SSH password access can be enabled.')
                verrors.add(*error)
            elif (
                await self.middleware.call('user.translate_username', old['username'])
            )['twofactor_auth_configured'] is False:
                verrors.add(*error)

    def __set_password(self, data):
        if 'password' not in data:
            return
        password = data.pop('password')
        if password:
            data['unixhash'] = crypted_password(password)
            data['smbhash'] = nt_password(password)
        else:
            data['unixhash'] = '*'
            data['smbhash'] = '*'

        return data

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

    @api_method(UserSetPasswordArgs, UserSetPasswordResult,
                audit='Set account password', audit_extended=lambda data: data['username'],
                authorization_required=False)
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

        NOTE: users authenticated with a one-time password will be able
        to change the password without submitting a second time.
        """

        verrors = ValidationErrors()
        is_full_admin = credential_has_full_admin(app.authenticated_credentials)
        is_otp_login = False
        authenticated_user = None

        if app.authenticated_credentials.is_user_session:
            authenticated_user = app.authenticated_credentials.user['username']
            if 'OTPW' in app.authenticated_credentials.user['account_attributes']:
                is_otp_login = True

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

        # Require submitting password twice if this is not a full admin session
        # and does not have a one-time password.
        if not is_full_admin and not is_otp_login:
            if data['old_password'] is None:
                verrors.add(
                    'user.set_password.old_password',
                    'FULL_ADMIN role is required in order to bypass check for current password.'
                )
            else:
                pam_resp = await self.middleware.call(
                    'auth.libpam_authenticate', username, data['old_password']
                )
                if pam_resp['code'] != pam.PAM_SUCCESS:
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
            await self.middleware.call('smb.update_passdb_user', entry)


class GroupModel(sa.Model):
    __tablename__ = 'account_bsdgroups'

    id = sa.Column(sa.Integer(), primary_key=True)
    bsdgrp_gid = sa.Column(sa.Integer())
    bsdgrp_group = sa.Column(sa.String(120), unique=True)
    bsdgrp_builtin = sa.Column(sa.Boolean(), default=False)
    bsdgrp_sudo_commands = sa.Column(sa.JSON(list))
    bsdgrp_sudo_commands_nopasswd = sa.Column(sa.JSON(list))
    bsdgrp_smb = sa.Column(sa.Boolean(), default=True)
    bsdgrp_userns_idmap = sa.Column(sa.Integer(), default=USERNS_IDMAP_NONE)
    bsdgrp_users = relationship('UserModel', secondary=lambda: GroupMembershipModel.__table__, overlaps='bsdusr_groups')


class GroupService(CRUDService):

    class Config:
        datastore = 'account.bsdgroups'
        datastore_prefix = 'bsdgrp_'
        datastore_extend = 'group.group_extend'
        datastore_extend_context = 'group.group_extend_context'
        cli_namespace = 'account.group'
        role_prefix = 'ACCOUNT'
        entry = GroupEntry

    @private
    async def group_extend_context(self, rows, extra):
        privileges = await self.middleware.call('datastore.query', 'account.privilege')

        users = await self.middleware.call('datastore.query', 'account.bsdusers')
        primary_memberships = defaultdict(set)
        for u in users:
            primary_memberships[u['bsdusr_group']['id']].add(u['id'])

        server_sid = await self.middleware.call('smb.local_server_sid')

        return {
            "privileges": privileges,
            "primary_memberships": primary_memberships,
            "server_sid": server_sid,
        }

    @private
    async def group_extend(self, group, ctx):
        group['name'] = group['group']
        group['users'] = list({u['id'] for u in group['users']} | ctx['primary_memberships'][group['id']])

        privilege_mappings = privileges_group_mapping(ctx['privileges'], [group['gid']], 'local_groups')

        if group['userns_idmap'] == USERNS_IDMAP_DIRECT:
            group['userns_idmap'] = 'DIRECT'
        elif group['userns_idmap'] == USERNS_IDMAP_NONE:
            group['userns_idmap'] = None

        match group['group']:
            case 'builtin_administrators':
                sid = f'{ctx["server_sid"]}-{DomainRid.ADMINS}'
            case 'builtin_guests':
                sid = f'{ctx["server_sid"]}-{DomainRid.GUESTS}'
            case _:
                if group['smb']:
                    sid = f'{ctx["server_sid"]}-{db_id_to_rid(IDType.GROUP, group["id"])}'
                else:
                    sid = None

        group.update({
            'local': True,
            'id_type_both': False,
            'sid': sid,
            'roles': privilege_mappings['roles']
        })
        return group

    @private
    async def group_compress(self, group):
        to_remove = [
            'name',
            'local',
            'id_type_both',
            'sid',
            'roles'
        ]

        match group.get('userns_idmap'):
            case 'DIRECT':
                group['userns_idmap'] = USERNS_IDMAP_DIRECT
            case None:
                group['userns_idmap'] = USERNS_IDMAP_NONE
            case _:
                pass

        for i in to_remove:
            group.pop(i, None)

        return group

    async def query(self, filters, options):
        """
        Query groups with `query-filters` and `query-options`.
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

        if filters_include_ds_accounts(filters):
            ds = await self.middleware.call('directoryservices.status')
            if ds['type'] is not None and ds['status'] == DSStatus.HEALTHY.name:
                ds_groups = await self.middleware.call('directoryservices.cache.query', 'GROUP', filters, options)

        result = await self.middleware.call(
            'datastore.query', self._config.datastore, [], datastore_options
        )

        return await self.middleware.run_in_thread(
            filter_list, result + ds_groups, filters, options
        )

    @api_method(GroupCreateArgs, GroupCreateResult, audit='Create group', audit_extended=lambda data: data['name'])
    async def do_create(self, data):
        """
        Create a new group.
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

        group = await self.group_compress(group)
        pk = await self.middleware.call('datastore.insert', 'account.bsdgroups', group, {'prefix': 'bsdgrp_'})

        if reload_users:
            await self.middleware.call('service.reload', 'user')

        if data['smb']:
            await self.middleware.call('smb.add_groupmap', group | {'id': pk})

        return pk

    @api_method(GroupUpdateArgs, GroupUpdateResult, audit='Update group', audit_callback=True)
    async def do_update(self, audit_callback, pk, data):
        """
        Update attributes of an existing group.
        """

        if pk > BASE_SYNTHETIC_DATASTORE_ID:
            # datastore ids for directory services are created by adding the
            # posix ID to a base value so that we can use getpwuid / getgrgid to
            # convert back to a username / group name
            try:
                groupname = (await self.middleware.call(
                    'group.get_group_obj', {'gid': pk - BASE_SYNTHETIC_DATASTORE_ID}
                ))['gr_name']
            except KeyError:
                groupname = 'UNKNOWN'

            audit_callback(groupname)
            raise CallError(
                'Groups provided by a directory service must be modified through the identity provider '
                '(LDAP server or domain controller).', errno.EPERM
            )

        group = await self.get_instance(pk)
        audit_callback(group['name'])

        if data.get('gid') == group['gid']:
            data.pop('gid')  # Only check for duplicate GID if we are updating it

        verrors = ValidationErrors()
        await self.__common_validation(verrors, data, 'group_update', pk=pk)
        if group['builtin']:
            # Generally many features of builtin groups should be immutable
            for key in ('sudo_commands', 'sudo_commands_nopasswd', 'smb', 'name'):
                if data.get(key, None) is not None and data[key] != group[key]:
                    verrors.add(
                        f'group_update.{key}',
                        'This configuration parameter may not be changed for builtin groups.'
                    )

            if data.get('users', None) is not None and data['users'] != group['users']:
                if group['gid'] not in ALLOWED_BUILTIN_GIDS:
                    verrors.add(
                        'group_update.users',
                        'Group membership for this builtin group may not be changed.'
                    )

        verrors.check()
        old_smb = group['smb']

        group.update(data)
        new_smb = group['smb']

        if 'name' in data and data['name'] != group['group']:
            group['group'] = group.pop('name')
            if new_smb:
                # group renamed. We can simply add over top since group_mapping.tdb is keyed
                # by SID value
                await self.middleware.call('smb.add_groupmap', group)
        else:
            group.pop('name', None)
            if new_smb and not old_smb:
                await self.middleware.call('smb.add_groupmap', group)
            elif old_smb and not new_smb:
                await self.middleware.call('smb.del_groupmap', group['id'])

        if 'users' in group:
            primary_users = {
                u['id']
                for u in await self.middleware.call(
                    'datastore.query',
                    'account.bsdusers',
                    [('bsdusr_group', '=', pk)],
                )
            }
            group['users'] = [u for u in group['users'] if u not in primary_users]

        group = await self.group_compress(group)
        await self.middleware.call('datastore.update', 'account.bsdgroups', pk, group, {'prefix': 'bsdgrp_'})

        await self.middleware.call('service.reload', 'user')
        return pk

    @api_method(GroupDeleteArgs, GroupDeleteResult, audit='Delete group', audit_callback=True)
    async def do_delete(self, audit_callback, pk, options):
        """
        Delete group `id`.

        The `delete_users` option deletes all users that have this group as their primary group.
        """

        if pk > BASE_SYNTHETIC_DATASTORE_ID:
            # datastore ids for directory services are created by adding the
            # posix ID to a base value so that we can use getpwuid / getgrgid to
            # convert back to a username / group name
            try:
                groupname = (await self.middleware.call(
                    'group.get_group_obj', {'gid': pk - BASE_SYNTHETIC_DATASTORE_ID}
                ))['gr_name']
            except KeyError:
                groupname = 'UNKNOWN'

            audit_callback(groupname)
            raise CallError(
                'Groups provided by a directory service must be deleted from the identity provider '
                '(LDAP server or domain controller).', errno.EPERM
            )

        group = await self.get_instance(pk)
        audit_callback(group['name'] + (' and all users that have this group as their primary group'
                                        if options['delete_users'] else ''))

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
            await self.middleware.call('smb.del_groupmap', group['id'])

        await self.middleware.call('service.reload', 'user')
        try:
            await self.middleware.call('idmap.gencache.del_idmap_cache_entry', {
                'entry_type': 'GID2SID',
                'entry': group['gid']
            })
        except MatchNotFound:
            pass

        return pk

    @api_method(GroupGetNextGidArgs, GroupGetNextGidResult, roles=['ACCOUNT_READ'])
    async def get_next_gid(self):
        """
        Get the next available/free gid.
        """
        used_gids = {
            group['bsdgrp_gid']
            for group in await self.middleware.call('datastore.query', 'account.bsdgroups')
        }
        used_gids |= set((await self.middleware.call('privilege.used_local_gids')).keys())

        # We should start gid from 3000 to avoid potential conflicts - Reference: NAS-117892
        next_gid = 3000
        while next_gid in used_gids:
            next_gid += 1

        return next_gid

    @api_method(GroupGetGroupObjArgs, GroupGetGroupObjResult, roles=['ACCOUNT_READ'])
    def get_group_obj(self, data):
        """
        Returns dictionary containing information from struct grp for the group specified by either
        the `groupname` or `gid`.

        If `sid_info` is specified then addition SMB / domain information is returned for the
        group.
        """
        verrors = ValidationErrors()
        if not data['groupname'] and data['gid'] is None:
            verrors.add('get_group_obj.groupname', 'Either "groupname" or "gid" must be specified')
        if data['groupname'] and data['gid'] is not None:
            verrors.add('get_group_obj.groupname', '"groupname" and "gid" may not be simultaneously specified')
        verrors.check()

        # NOTE: per request from UI team we are overriding default library
        # KeyError message with a clearer one
        #
        # Many callers to group.get_group_obj may be catching KeyError and so
        # changing exception type is something that should be approached
        # carefully.
        if data['groupname']:
            try:
                grp_obj = grp.getgrnam(data['groupname'], as_dict=True)
            except KeyError:
                raise KeyError(f'{data["groupname"]}: group with this name does not exist') from None
        else:
            try:
                grp_obj = grp.getgrgid(data['gid'], as_dict=True)
            except KeyError:
                raise KeyError(f'{data["gid"]}: group with this id does not exist') from None

        grp_obj['local'] = grp_obj['source'] == NssModule.FILES.name
        match grp_obj['source']:
            case NssModule.FILES.name:
                grp_obj['source'] = 'LOCAL'
            case NssModule.WINBIND.name:
                grp_obj['source'] = 'ACTIVEDIRECTORY'
            case NssModule.SSS.name:
                grp_obj['source'] = 'LDAP'
            case _:
                self.logger.error('%s: unknown ID source.', grp_obj['source'])
                raise ValueError(f'{grp_obj["source"]}: unknown ID source. Please file a bug report.')

        grp_obj['local'] = grp_obj['source'] == 'LOCAL'

        if data['sid_info']:
            sid = None

            match grp_obj['source']:
                case 'LOCAL':
                    idmap_ctx = None
                    db_entry = self.middleware.call_sync('group.query', [
                        ['group', '=', grp_obj['gr_name']],
                        ['local', '=', True]
                    ], {'select': ['sid']})
                    if not db_entry:
                        self.logger.error(
                            '%s: local group exists on server but does not exist in the '
                            'the group account table.', grp_obj['gr_name']
                        )
                    else:
                        sid = db_entry[0]['sid']
                case 'ACTIVEDIRECTORY':
                    # winbind provides idmapping for AD groups
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
                case 'LDAP':
                    # SSSD provides ID mapping for IPA domains
                    idmap_ctx = idmap_sss.SSSClient()
                case _:
                    self.logger.error('%s: unknown ID source.', grp_obj['source'])
                    raise ValueError(f'{grp_obj["source"]}: unknown ID source. Please file a bug report.')

            if idmap_ctx is not None:
                try:
                    sid = idmap_ctx.uidgid_to_idmap_entry({
                        'id_type': 'GROUP',
                        'id': grp_obj['gr_gid']
                    })['sid']
                except MatchNotFound:
                    # This can happen if IPA and group doesn't have SID assigned
                    sid = None

            grp_obj['sid'] = sid
        else:
            grp_obj['sid'] = None

        return grp_obj

    async def __common_validation(self, verrors, data, schema, pk=None):

        exclude_filter = [('id', '!=', pk)] if pk else []

        if data.get('smb') and not await self.middleware.call('smb.is_configured'):
            verrors.add(
                f'{schema}.smb', 'SMB groups may not be configured while SMB service backend is unitialized.'
            )

        if data.get('userns_idmap') and pk:
            entry = await self.query([['local', '=', True], ['id', '=', pk]], {'get': True})
            if entry['roles']:
                verrors.add(
                    f'{schema}.userns_idmap',
                    'User namespace idmaps may not be configured for privileged accounts.'
                )

            if entry['builtin']:
                verrors.add(
                    f'{schema}.userns_idmap',
                    'User namespace idmaps may not be configured for builtin accounts.'
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

        if data.get('gid') is not None:
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

            if privilege := (await self.middleware.call('privilege.used_local_gids')).get(data['gid']):
                verrors.add(
                    f'{schema}.gid',
                    f'A privilege {privilege["name"]!r} already uses this group ID.',
                    errno.EINVAL,
                )

        for idx, dbid in enumerate(data.get('users', [])):
            if dbid >= BASE_SYNTHETIC_DATASTORE_ID:
                verrors.add(
                    f'{schema}.users.{idx}',
                    'Directory services users may not be added as members of local groups.'
                )
                return

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
    try:
        # ensure that our default home path is always immutable. If it's not immutable then
        # pam_mkhomedir will start creating dirs within it on user login
        await middleware.call('filesystem.set_zfs_attributes', {
            'path': DEFAULT_HOME_PATH,
            'zfs_file_attributes': {'immutable': True}
        })
    except Exception:
        middleware.logger.error('Failed to set immutable property on %r', DEFAULT_HOME_PATH, exc_info=True)

    if await middleware.call('keyvalue.get', 'run_migration', False):
        await middleware.call('user.sync_builtin')
