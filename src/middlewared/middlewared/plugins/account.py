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

from asyncio import Lock as AsyncioLock
from dataclasses import asdict
from datetime import datetime
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
from middlewared.service import CallError, CRUDService, ValidationErrors, private, job
from middlewared.service_exception import MatchNotFound
import middlewared.sqlalchemy as sa
from middlewared.utils import run
from middlewared.utils.account.authenticator import UserPamAuthenticator, AccountFlag
from middlewared.utils.account.faillock import tally_locked_users, reset_tally
from middlewared.utils.crypto import generate_nt_hash, sha512_crypt, generate_string, check_unixhash
from middlewared.utils.directoryservices.constants import DSType, DSStatus
from middlewared.utils.filesystem.copy import copytree, CopyTreeConfig
from middlewared.utils.filter_list import filter_list
from middlewared.utils.nss import pwd, grp
from middlewared.utils.nss.nss_common import NssModule
from middlewared.utils.privilege import credential_has_full_admin, privileges_group_mapping
from middlewared.async_validators import check_path_resides_within_volume
from middlewared.utils.reserved_ids import ReservedXid
from middlewared.utils.security import (
    check_password_complexity,
    MAX_PASSWORD_HISTORY,
    PASSWORD_PROMPT_AGE,
)
from middlewared.utils.sid import db_id_to_rid, DomainRid
from middlewared.utils.time_utils import utc_now, UTC
from middlewared.plugins.account_.constants import (
    ADMIN_UID, ADMIN_GID, SKEL_PATH, DEFAULT_HOME_PATH,
    USERNS_IDMAP_DIRECT, USERNS_IDMAP_NONE, ALLOWED_BUILTIN_GIDS,
    SYNTHETIC_CONTAINER_ROOT, NO_LOGIN_SHELL, MIN_AUTO_XID
)
from middlewared.plugins.smb_.constants import SMBBuiltin
from middlewared.plugins.idmap_.idmap_constants import (
    BASE_SYNTHETIC_DATASTORE_ID,
    IDType,
)
from middlewared.plugins.idmap_ import idmap_winbind
from middlewared.plugins.idmap_ import idmap_sss
from threading import Lock


SYNC_NEXT_UID_LOCK = Lock()
ASYNC_NEXT_GID_LOCK = AsyncioLock()


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
    bsdusr_last_password_change = sa.Column(sa.Integer(), nullable=True)
    bsdusr_password_history = sa.Column(sa.EncryptedText(), default=[], nullable=True)


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

    ReservedUids = ReservedXid({})

    @private
    async def user_extend_context(self, rows, extra):
        groups = await self.middleware.call('group.query', [['local', '=', True]], {'select': ['id', 'name', 'roles']})

        user_api_keys = defaultdict(list)
        for key in await self.middleware.call('api_key.query'):
            if not key['local']:
                continue

            user_api_keys[key['username']].append(key['id'])

        sec = await self.middleware.call('system.security.config')
        if sec['enable_gpos_stig']:
            # When GPOS stig is enabled it's possible that users are locked due to pam_faillock(8)
            pam_locked_users = await self.middleware.run_in_thread(tally_locked_users)
        else:
            pam_locked_users = set()

        return {
            'now': utc_now(naive=False),
            'security': sec,
            'pam_locked_users': pam_locked_users,
            'server_sid': await self.middleware.call('smb.local_server_sid'),
            'user_2fa_mapping': ({
                entry['user']['id']: bool(entry['secret']) for entry in await self.middleware.call(
                    'datastore.query', 'account.twofactor_user_auth', [['user_id', '!=', None]]
                )
            }),
            'user_api_keys': user_api_keys,
            'roles_mapping': {i['id']: i['roles'] for i in groups},
            'group_ids': {i['name']: i['id'] for i in groups},
        }

    @private
    def _read_authorized_keys(self, homedir):
        # Extravagant zpool / hardware errors may manifest as IO errors during filesystem operations (even though the
        # pool itself imports). Since this is a hot codepath in the user_extend method (which *must not* fail) we
        # suppress the IOError here, and allow other filesystem operations to complain loudly at the user.
        with suppress(FileNotFoundError, IOError):
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

        if user['password_history']:
            user['password_history'] = user['password_history'].split()
        else:
            user['password_history'] = []

        if user['last_password_change'] is not None:
            user['last_password_change'] = datetime.fromtimestamp(user['last_password_change'], UTC)
            user['password_age'] = (ctx['now'] - user['last_password_change']).days
            if user['password_age'] < 0:
                # This means user is from the future. We don't want negative
                # ages and so we'll set this to None to differentiate from
                # accounts that are brand new
                user['password_age'] = None
        else:
            user['password_age'] = None

        # Set bool indicating user needs to change password
        # Depending on security configuration this can be a soft limit
        # that still allows login or a hard limit that blocks auth
        if user['password_age'] and ctx['security']['max_password_age']:
            max_age = ctx['security']['max_password_age']
            user['password_change_required'] = user['password_age'] >= (max_age - PASSWORD_PROMPT_AGE)
        else:
            user['password_change_required'] = False

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
            'sid': sid,
            'roles': list(user_roles),
            'api_keys': ctx['user_api_keys'][user['username']]
        })
        if ctx['security']['enable_gpos_stig']:
            # NTLM authentication relies on non-FIPS crypto
            user.update({
                'smb': False,
                'sid': None,
                'smbhash': '*'
            })
            if user['username'] in ctx['pam_locked_users']:
                user['locked'] = True

        user['webshare'] = ctx['group_ids']['truenas_webshare'] in user['groups']

        return user

    @private
    def user_compress(self, user):
        to_remove = [
            'api_keys',
            'local',
            'sid',
            'immutable',
            'home_create',
            'roles',
            'random_password',
            'twofactor_auth_configured',
            'password_age',
            'password_change_required',
            'webshare',
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

        for key in ['last_password_change', 'account_expiration_date']:
            if user.get(key) is None:
                continue

            user[key] = int(user[key].timestamp())

        if user.get('password_history') is not None:
            user['password_history'] = ' '.join(user['password_history'])

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
                        # We do not cache 2FA mappings since they have security implications
                        # So they need to be reapplied on every user.query call
                        ad_users_2fa_mapping = set(await self.middleware.call('auth.twofactor.get_ad_users'))
                        if ad_users_2fa_mapping:
                            for u in ds_users:
                                u['twofactor_auth_configured'] = u['sid'] in ad_users_2fa_mapping
                    case _:
                        # FIXME - map twofactor_auth_configured hint for LDAP users
                        pass

        result = await self.middleware.call(
            'datastore.query', self._config.datastore, [], datastore_options
        )

        # Add a synthetic user for the root account in containers
        container_root = await self.middleware.call('idmap.synthetic_user', SYNTHETIC_CONTAINER_ROOT.copy(), None)
        # NOTE: we deliberately don't include a userns_idmap value here because it is
        # implicit when we set up subuid for container
        container_root.update({'builtin': True, 'local': True, 'locked': True, 'smb': False})

        return await self.middleware.run_in_thread(
            filter_list, result + ds_users + [container_root], filters, options
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

        if data['home'] == DEFAULT_HOME_PATH:
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
            not data['group'] and not data['group_create']
        ) or (
            data['group'] is not None and data['group_create']
        ):
            verrors.add(
                'user_create.group',
                'Enter either a group name or create a new group to '
                'continue.',
                errno.EINVAL
            )

        group_ids = []
        if data['group']:
            group_ids.append(data['group'])
        group_ids.extend(data['groups'])

        self.middleware.call_sync('user.common_validation', verrors, data, 'user_create', group_ids)

        if data['sshpubkey'] and not data['home'].startswith('/mnt'):
            verrors.add(
                'user_create.sshpubkey',
                f'{data["home"]}: the user home directory must be set to a writable path located within a data pool.'
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
                verrors.add('user_create.group', f'Group {data["group"]} not found', errno.ENOENT)
            else:
                group = group[0]
        verrors.check()

        if data['smb']:
            data['groups'].append((self.middleware.call_sync(
                'group.query', [('group', '=', 'builtin_users'), ('local', '=', True)], {'get': True},
            ))['id'])

        if data['uid'] is None:
            data['uid'] = self.get_next_uid()

        new_homedir = False
        home_mode = data.pop('home_mode')
        if data['home'] and data['home'] != DEFAULT_HOME_PATH:
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

                with SYNC_NEXT_UID_LOCK:
                    self.ReservedUids.remove_entry(data['uid'])

                raise

        self.handle_webshare(data)

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
        finally:
            with SYNC_NEXT_UID_LOCK:
                self.ReservedUids.remove_entry(data['uid'])

        self.middleware.call_sync('service.control', 'RELOAD', 'ssh').wait_sync(raise_error=True)
        self.middleware.call_sync('service.control', 'RELOAD', 'user').wait_sync(raise_error=True)

        if data['smb']:
            self.middleware.call_sync('smb.update_passdb_user', data | {'id': pk})

        if os.path.isdir(SKEL_PATH) and os.path.exists(data['home']) and data['home'] != DEFAULT_HOME_PATH:
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

    @api_method(UserUpdateArgs, UserUpdateResult, audit='Update user', audit_callback=True, pass_app=True)
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
            if data['group'] is None:
                # sending `group` as None is okay in user.create since
                # it means, during user creation, a new primary group
                # will automatically be created for said user. However,
                # on update, a user MUST have a primary group. If someone
                # tries to send an explicit None value here, let's raise
                # an informative validation error.
                verrors.add('user_update.group', 'User must have a primary group', errno.EINVAL)
            else:
                group = self.middleware.call_sync('datastore.query', 'account.bsdgroups', [
                    ('id', '=', data['group'])
                ])
                if not group:
                    verrors.add('user_update.group', f'Group {data["group"]} not found', errno.ENOENT)
                else:
                    group = group[0]
        else:
            group = user['group']
            user['group'] = group['id']
        verrors.check()

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

        # NAS-136301: prevent locking all admin accounts
        if data.get('locked') is True:
            number_admin_remaining = self.middleware.call_sync(
                'user.query', [
                    ['roles', 'rin', 'FULL_ADMIN'],
                    ['local', '=', True],
                    ['locked', '=', False],
                    ['id', '!=', user['id']]
                ],
                {'count': True}
            )
            if 0 >= number_admin_remaining:
                verrors.add('user_update.locked',
                            'After locking this user no local users will have FULL_ADMIN role')

        self.middleware.call_sync('user.common_validation', verrors, data, 'user_update', group_ids, user)

        try:
            st = os.stat(user.get("home", DEFAULT_HOME_PATH)).st_mode
            old_mode = f'{stat.S_IMODE(st):03o}'
        except FileNotFoundError:
            old_mode = None

        home = data.get('home') or user['home']
        had_home = user['home'] != DEFAULT_HOME_PATH
        has_home = home != DEFAULT_HOME_PATH
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
            if user['uid'] in (0, ADMIN_UID):
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

        self.handle_webshare(user)

        user = self.user_compress(user)
        self.middleware.call_sync('datastore.update', 'account.bsdusers', pk, user, {'prefix': 'bsdusr_'})

        reset_tally(user['username'])
        self.middleware.call_sync('service.control', 'RELOAD', 'ssh').wait_sync(raise_error=True)
        self.middleware.call_sync('service.control', 'RELOAD', 'user').wait_sync(raise_error=True)
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

    @api_method(UserDeleteArgs, UserDeleteResult, audit='Delete user', audit_callback=True, pass_app=True)
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

        if user['home'] and user['home'] != DEFAULT_HOME_PATH:
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
        self.middleware.call_sync('service.control', 'RELOAD', 'ssh').wait_sync(raise_error=True)
        reset_tally(user['username'])
        self.middleware.call_sync('service.control', 'RELOAD', 'user').wait_sync(raise_error=True)
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

        :param group_ids: List of local group IDs for the user.
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
            NO_LOGIN_SHELL: 'nologin',
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

        # Return the container root if requestedt
        if data['username'] == SYNTHETIC_CONTAINER_ROOT['pw_name']:
            return SYNTHETIC_CONTAINER_ROOT.copy()
        elif data['uid'] == SYNTHETIC_CONTAINER_ROOT['pw_uid']:
            return SYNTHETIC_CONTAINER_ROOT.copy()

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
    def get_next_uid(self):
        """
        Get the next available/free uid.
        """
        # We want to create new users from 3000 to avoid potential conflicts - Reference: NAS-117892
        with SYNC_NEXT_UID_LOCK:
            allocated_uids = set([u['uid'] for u in self.middleware.call_sync(
                'datastore.query', 'account.bsdusers',
                [('builtin', '=', False), ('uid', '>=', MIN_AUTO_XID)], {'prefix': 'bsdusr_'}
            )])

            in_flight_uids = self.ReservedUids.in_use()

            total_uids = allocated_uids | in_flight_uids
            max_uid = max(total_uids) if total_uids else MIN_AUTO_XID - 1

            if gap_uids := set(range(MIN_AUTO_XID, max_uid)) - total_uids:
                next_uid = min(gap_uids)
            else:
                next_uid = max_uid + 1

            self.ReservedUids.add_entry(next_uid)
            return next_uid

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
        authentication_required=False,
        pass_app=True,
    )
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
    async def password_security_validate(self, schema, verrors, password, password_history, password_field='password'):
        # NOTE: min_password_age is *not* validated here because the system administator needs
        # to be able to reset passwords in case the user forgets theirs
        sec = await self.middleware.call('system.security.config')
        field = f'{schema}.{password_field}'
        if sec['password_complexity_ruleset']:
            unmet_rules = check_password_complexity(sec['password_complexity_ruleset'], password)
            if unmet_rules:
                verrors.add(
                    field,
                    'The specified password does not meet minimum complexity requirements. '
                    f'The following character types are absent: {", ".join(unmet_rules)}'
                )

        if sec['min_password_length'] and len(password) < sec['min_password_length']:
            verrors.add(
                field,
                'The specified password is too short. The minimum password length '
                f'is {sec["min_password_length"]} characters.'
            )

        if password_history and sec['password_history_length']:
            # the most recent hashes are at end of list and so we reverse order when evaluating whether there
            # is a repeat in the password history
            for idx, unix_hash in enumerate(reversed(password_history)):
                if idx >= sec['password_history_length']:
                    # History may be longer than currently configured history length
                    break

                if check_unixhash(password, unix_hash):
                    verrors.add(
                        field,
                        'The security configuration of the TrueNAS server requires a password '
                        f'that does not match any of the last {sec["password_history_length"]} '
                        'passwords for this account.'
                    )

    @private
    async def common_validation(
        self, verrors: ValidationErrors, data: dict, schema: str, group_ids: list[int], old: dict | None = None
    ) -> None:
        exclude_filter = [('id', '!=', old['id'])] if old else []
        combined = data if not old else old | data
        password_changed = False

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

        if data.get('random_password'):
            if data.get('password'):
                verrors.add(
                    f'{schema}.random_password',
                    'Requesting a randomized password while simultaneously supplying '
                    'an explicit password is not permitted.'
                )
            else:
                data['password'] = generate_string(string_size=20)
                password_changed = True

        elif data.get('password'):
            history = old['password_history'] + [old['unixhash']] if old else None
            await self.password_security_validate(schema, verrors, data['password'], history)
            password_changed = True

        if password_changed:
            data['last_password_change'] = utc_now(naive=False)

            # We store a number of hashes equal to the maximum possible value
            # of the password history parameter so that admins can bump the
            # history value up and have it take actual effect.
            if old:
                password_history = old['password_history'] or []
                password_history.append(old['unixhash'])
                while len(password_history) > MAX_PASSWORD_HISTORY:
                    password_history.pop(0)

                data['password_history'] = password_history

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

        stig_enabled = (await self.middleware.call('system.security.config'))['enable_gpos_stig']

        if combined['smb']:
            if not await self.middleware.call('smb.is_configured'):
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

            if combined['password_disabled']:
                verrors.add(
                    f'{schema}.password_disabled', 'Password authentication may not be disabled for SMB users.'
                )

            if stig_enabled:
                verrors.add(
                    f'{schema}.smb',
                    'SMB authentication for local user accounts is not permitted when General Purpose OS '
                    'STIG compatibility is enabled.'
                )

        if old:
            is_enabled_system_account = combined['immutable'] and any([
                not combined['password_disabled'], not combined['locked'], combined['unixhash'] != "*"
            ])

            if stig_enabled and is_enabled_system_account:
                verrors.add(
                    f'{schema}.immutable',
                    f'{combined["username"]} is a System Administrator account and is not permitted to be '
                    'enabled for password authentication when General Purpose OS STIG compatibility is enabled. '
                    'Please disable the password or lock the account.'
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
            elif combined['ssh_password_enabled']:
                verrors.add(f'{schema}.home', 'SSH password login requires a valid home path.')

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

        # Root user restrictions
        if old and old['uid'] == 0:  # Root user being updated
            # root user is not allowed access via webshare
            if data.get('webshare'):
                verrors.add(
                    f'{schema}.webshare',
                    'The root user is not allowed access via webshare.'
                )
            if 'groups' in data:
                # Get builtin_administrators group primary key (datastore id)
                builtin_admin_group = await self.middleware.call(
                    'datastore.query',
                    'account.bsdgroups',
                    [('group', '=', 'builtin_administrators')],
                    {'get': True, 'prefix': 'bsdgrp_'}
                )
                builtin_admin_pk = builtin_admin_group['id']

                new_groups = data['groups']

                # Rule 1: Cannot remove root from builtin_administrators
                if builtin_admin_pk not in new_groups:
                    verrors.add(
                        f'{schema}.groups',
                        'The root user must remain a member of the builtin_administrators group.'
                    )

                # Rule 2: Root can only be in builtin_administrators, no other groups
                if new_groups != [builtin_admin_pk]:
                    verrors.add(
                        f'{schema}.groups',
                        'The root user may only be a member of the builtin_administrators group.'
                    )

        if 'full_name' in data:
            for illegal_char in filter(lambda c: c in data['full_name'], (':', '\n')):
                verrors.add(f'{schema}.full_name', f'The {illegal_char!r} character is not allowed.')

        if 'shell' in data:
            if data['shell'] not in await self.middleware.call('user.shell_choices', group_ids):
                verrors.add(f'{schema}.shell', 'Please select a valid shell.')
            elif combined['ssh_password_enabled'] and data['shell'] == NO_LOGIN_SHELL:
                verrors.add(f'{schema}.shell', 'SSH password login requires a login shell.')

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

        if data.get('ssh_password_enabled'):
            two_factor_config = await self.middleware.call('auth.twofactor.config')
            if two_factor_config['enabled'] and two_factor_config['services']['ssh']:
                error = [
                    f'{schema}.ssh_password_enabled',
                    '2FA for this user needs to be explicitly configured before password based SSH access is enabled.'
                ]
                if old is None:
                    error[1] += (
                        ' User will be created with SSH password access disabled and after 2FA has been '
                        'configured for this user, SSH password access can be enabled.'
                    )
                    verrors.add(*error)
                elif (
                    await self.middleware.call('user.translate_username', old['username'])
                )['twofactor_auth_configured'] is False:
                    verrors.add(*error)
            if combined['home'] == DEFAULT_HOME_PATH or combined['shell'] == NO_LOGIN_SHELL:
                verrors.add(
                    f'{schema}.ssh_password_enabled',
                    'Cannot be enabled without a valid home path and login shell.'
                )

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
    def handle_webshare(self, data):
        webshare = self.middleware.call_sync(
            'datastore.query',
            'account.bsdgroups',
            [('group', '=', 'truenas_webshare')],
            {'prefix': 'bsdgrp_', 'get': True},
        )
        # root user is excluded from participating
        if data['webshare'] and (data['username'] != 'root'):
            if webshare['id'] not in data['groups']:
                data['groups'].append(webshare['id'])
        else:
            if webshare['id'] in data['groups']:
                data['groups'].remove(webshare['id'])

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
                authorization_required=False,
                pass_app=True, pass_app_require=True)
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
        password_aging_override = is_full_admin

        if app.authenticated_credentials.is_user_session:
            authenticated_user = app.authenticated_credentials.user['username']
            if AccountFlag.OTPW in app.authenticated_credentials.user['account_attributes']:
                is_otp_login = True

            if not password_aging_override:
                if AccountFlag.PASSWORD_CHANGE_REQUIRED in app.authenticated_credentials.user['account_attributes']:
                    password_aging_override = True

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
                # Create a temporary authentication context. Calling into auth.libpam_authenticate
                # would try to re-authenticate under the current session's authentication context,
                # which would fail.
                pam_hdl = UserPamAuthenticator()
                pam_resp = await self.middleware.run_in_thread(
                    pam_hdl.authenticate, username, data['old_password'], origin=app.origin
                )
                if pam_resp.code != pam.PAM_SUCCESS:
                    verrors.add(
                        'user.set_password.old_password',
                        f'{username}: failed to validate password.'
                    )

        history = entry['password_history'] + [entry['unixhash']]
        await self.password_security_validate('user.set_password', verrors, password, history, 'new_password')
        min_password_age = (await self.middleware.call('system.security.config'))['min_password_age']

        verrors.check()

        if not password_aging_override and min_password_age and entry['password_age'] < min_password_age:
            verrors.add(
                'user.set_password.username',
                f'{username}: password changed too recently. Minimum password age is: {min_password_age}'
            )

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
        entry['last_password_change'] = utc_now(naive=False)

        await self.middleware.call('datastore.update', 'account.bsdusers', entry['id'], {
            'bsdusr_unixhash': entry['unixhash'],
            'bsdusr_smbhash': entry['smbhash'],
            'bsdusr_password_history': ', '.join(history),
            'bsdusr_last_password_change': int(entry['last_password_change'].timestamp()),
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

    ReservedGids = ReservedXid({})

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

        is_immutable = group['builtin'] and group['gid'] not in ALLOWED_BUILTIN_GIDS

        group.update({
            'local': True,
            'sid': sid,
            'immutable': is_immutable,
            'roles': privilege_mappings['roles']
        })
        return group

    @private
    async def group_compress(self, group):
        to_remove = [
            'name',
            'local',
            'immutable',
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

        try:
            group = await self.group_compress(group)
            pk = await self.middleware.call('datastore.insert', 'account.bsdgroups', group, {'prefix': 'bsdgrp_'})
        finally:
            # Once the data store entry is created we can safely remove the reservation
            async with ASYNC_NEXT_GID_LOCK:
                self.ReservedGids.remove_entry(data['gid'])

        if reload_users:
            await (await self.middleware.call('service.control', 'RELOAD', 'user')).wait(raise_error=True)

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
        if group['immutable']:
            verrors.add('group_update.id', 'Immutable groups cannot be changed')

        elif group['builtin']:
            # Generally many features of builtin groups should be immutable
            for key in ('sudo_commands', 'sudo_commands_nopasswd', 'smb', 'name'):
                if data.get(key, None) is not None and data[key] != group[key]:
                    verrors.add(
                        f'group_update.{key}',
                        'This configuration parameter may not be changed for builtin groups.'
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

        await (await self.middleware.call('service.control', 'RELOAD', 'user')).wait(raise_error=True)
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

        await (await self.middleware.call('service.control', 'RELOAD', 'user')).wait(raise_error=True)
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
        async with ASYNC_NEXT_GID_LOCK:
            groups = await self.middleware.call(
                'datastore.query', 'account.bsdgroups', [['bsdgrp_gid', '>=', MIN_AUTO_XID], ['bsdgrp_builtin', '=', False]]
            )
            used_gids = set(group['bsdgrp_gid'] for group in groups)
            used_gids |= set([gid for gid in (await self.middleware.call('privilege.used_local_gids')).keys() if gid >= MIN_AUTO_XID])
            in_flight_gids = self.ReservedGids.in_use()
            total_gids = used_gids | in_flight_gids
            max_gid = max(total_gids) if total_gids else MIN_AUTO_XID - 1

            if gid_gap := (set(range(MIN_AUTO_XID, max_gid)) - total_gids):
                next_gid = min(gid_gap)
            else:
                next_gid = max_gid + 1

            self.ReservedGids.add_entry(next_gid)
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

        if 'userns_idmap' in data and pk:
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

        # Special handling for builtin_administrators group
        if pk and 'users' in data:
            group = await self.middleware.call('group.get_instance', pk)
            if group['group'] == 'builtin_administrators':
                # Get root user primary key (datastore id)
                root_user = await self.middleware.call(
                    'datastore.query',
                    'account.bsdusers',
                    [('username', '=', 'root')],
                    {'get': True, 'prefix': 'bsdusr_'}
                )
                root_user_pk = root_user['id']

                # Check if root is being removed from builtin_administrators
                if root_user_pk not in data['users']:
                    verrors.add(
                        f'{schema}.users',
                        'The root user must remain a member of the builtin_administrators group.'
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

    if await middleware.call2(middleware.services.keyvalue.get, 'run_migration', False):
        await middleware.call('user.sync_builtin')
