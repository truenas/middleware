from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
import errno
import os
import shutil
import stat
from threading import Lock
from typing import TYPE_CHECKING, Any

from middlewared.api.current import (
    GroupCreate,
    QueryOptions,
    UserCreate,
    UserCreateUpdateResult,
    UserDeleteOptions,
    UserEntry,
    UserGetUserObj,
    UserUpdate,
)
from middlewared.plugins.idmap_.idmap_constants import BASE_SYNTHETIC_DATASTORE_ID, IDType
from middlewared.service import CallError, CRUDServicePart, ServiceContext, ValidationErrors
from middlewared.service_exception import InstanceNotFound, MatchNotFound
import middlewared.sqlalchemy as sa
from middlewared.utils.account.faillock import reset_tally, tally_locked_users
from middlewared.utils.directoryservices.constants import DSStatus, DSType
from middlewared.utils.filter_list import filter_list
from middlewared.utils.lang import undefined
from middlewared.utils.reserved_ids import ReservedXid
from middlewared.utils.security import PASSWORD_PROMPT_AGE
from middlewared.utils.sid import db_id_to_rid
from middlewared.utils.time_utils import utc_now
from middlewared.utils.types import AuditCallback
from middlewared.utils.webshare import WEBSHARE_GROUP

from .constants import (
    ADMIN_UID,
    DEFAULT_HOME_PATH,
    MIN_AUTO_XID,
    SKEL_PATH,
    SYNTHETIC_CONTAINER_ROOT,
    USERNS_IDMAP_DIRECT,
    USERNS_IDMAP_NONE,
)
from .membership import GroupMembershipModel
from .password import set_password_hashes
from .user_home import read_authorized_keys, recreate_homedir_if_not_exists, setup_homedir, update_sshpubkey
from .user_validate import (
    PasswordUpdate,
    common_validation,
    supplied,
    supplied_flag,
    supplied_or_none,
    validate_sshpubkey_home_access,
    validate_userns_idmap_conflict,
)
from .utils import filters_include_ds_accounts, userns_idmap_to_db

if TYPE_CHECKING:
    from middlewared.api.base.server.app import App

__all__ = ("SYNC_NEXT_UID_LOCK", "UserModel", "UserServicePart")

SYNC_NEXT_UID_LOCK = Lock()


class UserModel(sa.Model):
    __tablename__ = "account_bsdusers"

    id = sa.Column(sa.Integer(), primary_key=True)
    bsdusr_uid = sa.Column(sa.Integer())
    bsdusr_username = sa.Column(sa.String(16), default="User &", unique=True)
    bsdusr_unixhash = sa.Column(sa.String(128), default="*")
    bsdusr_smbhash = sa.Column(sa.EncryptedText(), default="*")
    bsdusr_home = sa.Column(sa.String(255), default=DEFAULT_HOME_PATH)
    bsdusr_shell = sa.Column(sa.String(120), default="/bin/csh")
    bsdusr_full_name = sa.Column(sa.String(120))
    bsdusr_builtin = sa.Column(sa.Boolean(), default=False)
    bsdusr_smb = sa.Column(sa.Boolean(), default=True)
    bsdusr_userns_idmap = sa.Column(sa.Integer(), default=USERNS_IDMAP_NONE)
    bsdusr_password_disabled = sa.Column(sa.Boolean(), default=False)
    bsdusr_ssh_password_enabled = sa.Column(sa.Boolean(), default=False)
    bsdusr_locked = sa.Column(sa.Boolean(), default=False)
    bsdusr_sudo_commands = sa.Column(sa.JSON(list))
    bsdusr_sudo_commands_nopasswd = sa.Column(sa.JSON(list))
    bsdusr_group_id = sa.Column(sa.ForeignKey("account_bsdgroups.id"), index=True)
    bsdusr_email = sa.Column(sa.String(254), nullable=True)
    bsdusr_groups: sa.Mapped[list[Any]] = sa.relationship(
        "GroupModel",
        secondary=lambda: GroupMembershipModel.__table__,
    )
    bsdusr_last_password_change = sa.Column(sa.Integer(), nullable=True)
    bsdusr_password_history = sa.Column(sa.EncryptedText(), default=[], nullable=True)


def group_ids_to_gids(context: ServiceContext, group_ids: list[int]) -> list[int]:
    return [group.gid for group in context.call_sync2(context.s.group.query, [["id", "in", list(group_ids)]])]


def webshare_membership(
    context: ServiceContext,
    *,
    webshare: bool,
    username: str,
    groups: list[int],
) -> list[int]:
    """`groups` with the webshare group added or removed so it matches `webshare`.

    The root user never participates, whatever was asked for.
    """
    entry = context.middleware.call_sync(
        "datastore.query",
        "account.bsdgroups",
        [("group", "=", WEBSHARE_GROUP)],
        {"prefix": "bsdgrp_", "get": True},
    )
    result = list(groups)
    if webshare and username != "root":
        if entry["id"] not in result:
            result.append(entry["id"])
    elif entry["id"] in result:
        result.remove(entry["id"])

    return result


def apply_password_update(row: dict[str, Any], update: PasswordUpdate) -> None:
    """Write the password columns `update` resolved onto a datastore `row`."""
    if update.set_hashes:
        row["password"] = update.password
        set_password_hashes(row)

    if update.last_password_change is not None:
        row["last_password_change"] = int(update.last_password_change.timestamp())

    if update.password_history is not None:
        row["password_history"] = " ".join(update.password_history)


class UserServicePart(CRUDServicePart[UserEntry]):
    _datastore = "account.bsdusers"
    _datastore_prefix = "bsdusr_"
    _entry = UserEntry

    def __init__(self, context: ServiceContext) -> None:
        super().__init__(context)
        self.reserved_uids = ReservedXid({})

    async def extend_context(self, rows: list[dict[str, Any]], extra: dict[str, Any]) -> dict[str, Any]:
        groups = await self.call2(
            self.s.group.query,
            [["local", "=", True]],
            QueryOptions(select=["id", "name", "roles"]),
        )

        user_api_keys = defaultdict(list)
        for key in await self.call2(self.s.api_key.query):
            if not key.local:
                continue

            user_api_keys[key.username].append(key.id)

        sec = await self.call2(self.s.system.security.config)
        if sec.enable_gpos_stig:
            # When GPOS stig is enabled it's possible that users are locked due to pam_faillock(8)
            pam_locked_users = await self.to_thread(tally_locked_users)
        else:
            pam_locked_users = set()

        return {
            "now": utc_now(naive=False),
            "security": sec,
            "pam_locked_users": pam_locked_users,
            "server_sid": await self.middleware.call("smb.local_server_sid"),
            "user_2fa_mapping": {
                entry["user"]["id"]: bool(entry["secret"])
                for entry in await self.middleware.call(
                    "datastore.query", "account.twofactor_user_auth", [["user_id", "!=", None]]
                )
            },
            "user_api_keys": user_api_keys,
            "roles_mapping": {group.id: group.roles for group in groups},
            "group_ids": {group.name: group.id for group in groups},
        }

    async def extend(self, user: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        user["groups"] = [g["id"] for g in user["groups"]]

        # Normalize email, empty is really null
        if user["email"] == "":
            user["email"] = None

        # Get authorized keys
        user["sshpubkey"] = await self.to_thread(read_authorized_keys, self, user["home"])

        user["immutable"] = user["builtin"] or (user["uid"] == ADMIN_UID)
        user["twofactor_auth_configured"] = bool(ctx["user_2fa_mapping"].get(user["id"]))

        if user["userns_idmap"] == USERNS_IDMAP_DIRECT:
            user["userns_idmap"] = "DIRECT"
        elif user["userns_idmap"] == USERNS_IDMAP_NONE:
            user["userns_idmap"] = None

        if user["password_history"]:
            user["password_history"] = user["password_history"].split()
        else:
            user["password_history"] = []

        if user["last_password_change"] is not None:
            user["last_password_change"] = datetime.fromtimestamp(user["last_password_change"], UTC)
            user["password_age"] = (ctx["now"] - user["last_password_change"]).days
            if user["password_age"] < 0:
                # This means user is from the future. We don't want negative
                # ages and so we'll set this to None to differentiate from
                # accounts that are brand new
                user["password_age"] = None
        else:
            user["password_age"] = None

        # Set bool indicating user needs to change password
        # Depending on security configuration this can be a soft limit
        # that still allows login or a hard limit that blocks auth
        if user["password_age"] and ctx["security"].max_password_age:
            max_age = ctx["security"].max_password_age
            user["password_change_required"] = user["password_age"] >= (max_age - PASSWORD_PROMPT_AGE)
        else:
            user["password_change_required"] = False

        user_roles = set()
        for g in user["groups"] + [user["group"]["id"]]:
            if not (entry := ctx["roles_mapping"].get(g)):
                continue

            user_roles |= set(entry)

        if user["smb"]:
            sid = f"{ctx['server_sid']}-{db_id_to_rid(IDType.USER, user['id'])}"
        else:
            sid = None

        user.update(
            {
                "local": True,
                "sid": sid,
                "roles": list(user_roles),
                "api_keys": ctx["user_api_keys"][user["username"]],
            }
        )
        if ctx["security"].enable_gpos_stig:
            # NTLM authentication relies on non-FIPS crypto
            user.update({"smb": False, "sid": None, "smbhash": "*"})
            if user["username"] in ctx["pam_locked_users"]:
                user["locked"] = True

        user["webshare"] = ctx["group_ids"][WEBSHARE_GROUP] in user["groups"]

        return user

    async def _query_rows(
        self,
        filters: list[Any],
        options: QueryOptions,
        extra: dict[str, Any],
    ) -> list[dict[str, Any]]:
        rows = await super()._query_rows(filters, options, extra)

        if filters_include_ds_accounts(filters):
            ds = await self.middleware.call("directoryservices.status")
            if ds["type"] is not None and ds["status"] == DSStatus.HEALTHY.name:
                # The cache stores whole `UserEntry` rows and applies `filters` itself, so these
                # must not be extended again.
                ds_users: list[dict[str, Any]] = await self.middleware.call(
                    "directoryservices.cache.query",
                    "USER",
                    filters,
                    options.model_dump(),
                )

                match DSType(ds["type"]):
                    case DSType.AD:
                        # We do not cache 2FA mappings since they have security implications
                        # So they need to be reapplied on every user.query call
                        ad_users_2fa_mapping = set(await self.middleware.call("auth.twofactor.get_ad_users"))
                        if ad_users_2fa_mapping:
                            for u in ds_users:
                                u["twofactor_auth_configured"] = u["sid"] in ad_users_2fa_mapping
                    case _:
                        # FIXME - map twofactor_auth_configured hint for LDAP users
                        pass

                rows += ds_users

        # Add a synthetic user for the root account in containers
        container_root = await self.middleware.call("idmap.synthetic_user", SYNTHETIC_CONTAINER_ROOT.copy(), None)
        # NOTE: we deliberately don't include a userns_idmap value here because it is
        # implicit when we set up subuid for container
        container_root.update({"builtin": True, "local": True, "locked": True, "smb": False})
        rows += filter_list([container_root], filters)

        return rows

    async def get_instance(self, id_: int, extra: dict[str, Any] | None = None) -> UserEntry:
        users = await self.query([[self._datastore_primary_key, "=", id_]])
        if not users:
            raise InstanceNotFound(f"User {id_} does not exist")

        return users[0]

    def get_next_uid(self) -> int:
        # We want to create new users from 3000 to avoid potential conflicts - Reference: NAS-117892
        with SYNC_NEXT_UID_LOCK:
            allocated_uids = {
                u["uid"]
                for u in self.middleware.call_sync(
                    "datastore.query",
                    "account.bsdusers",
                    [("builtin", "=", False), ("uid", ">=", MIN_AUTO_XID)],
                    {"prefix": "bsdusr_"},
                )
            }

            in_flight_uids = self.reserved_uids.in_use()

            total_uids = allocated_uids | in_flight_uids
            max_uid = max(total_uids) if total_uids else MIN_AUTO_XID - 1

            if gap_uids := set(range(MIN_AUTO_XID, max_uid)) - total_uids:
                next_uid = min(gap_uids)
            else:
                next_uid = max_uid + 1

            self.reserved_uids.add_entry(next_uid)
            return next_uid

    def _release_uid(self, uid: int) -> None:
        with SYNC_NEXT_UID_LOCK:
            self.reserved_uids.remove_entry(uid)

    def do_create(self, data: UserCreate) -> UserCreateUpdateResult:
        verrors = ValidationErrors()

        if (not data.group and not data.group_create) or (data.group is not None and data.group_create):
            verrors.add(
                "user_create.group",
                "Enter either a group name or create a new group to continue.",
                errno.EINVAL,
            )

        aux_groups = list(data.groups)
        group_ids = ([data.group] if data.group else []) + aux_groups

        password_update = self.run_coroutine(common_validation(self, verrors, data, "user_create", group_ids))

        if data.sshpubkey and not data.home.startswith("/mnt"):
            verrors.add(
                "user_create.sshpubkey",
                f"{data.home}: the user home directory must be set to a writable path located within a data pool.",
            )

        verrors.check()

        group_created = False

        if data.group_create:
            groups = self.call_sync2(
                self.s.group.query,
                [("group", "=", data.username), ("local", "=", True)],
            )
            if groups:
                group = groups[0]
            else:
                group_id = self.call_sync2(
                    self.s.group.create_internal,
                    GroupCreate(
                        name=data.username,
                        smb=False,
                        sudo_commands=[],
                        sudo_commands_nopasswd=[],
                    ),
                    False,
                )
                group = self.call_sync2(
                    self.s.group.query,
                    [("id", "=", group_id), ("local", "=", True)],
                    QueryOptions(get=True),
                )
                group_created = True
        else:
            groups = self.call_sync2(self.s.group.query, [("id", "=", data.group)])
            if not groups:
                verrors.add("user_create.group", f"Group {data.group} not found", errno.ENOENT)
                verrors.check()

            group = groups[0]

        if data.smb:
            aux_groups.append(
                self.call_sync2(
                    self.s.group.query,
                    [("group", "=", "builtin_users"), ("local", "=", True)],
                    QueryOptions(get=True),
                ).id
            )

        uid = data.uid
        if uid is None:
            uid = self.get_next_uid()

            # common_validation could not resolve a DIRECT mapping without a uid;
            # now that one was auto-assigned, recheck against existing idmap claims.
            idmap_verrors = ValidationErrors()
            self.run_coroutine(
                validate_userns_idmap_conflict(
                    self,
                    idmap_verrors,
                    "user_create",
                    data.userns_idmap,
                    uid,
                    None,
                )
            )
            if idmap_verrors:
                self._release_uid(uid)
                if group_created:
                    self.call_sync2(self.s.group.delete, group.id)
                idmap_verrors.check()

        home = data.home
        if data.sshpubkey and home and home != DEFAULT_HOME_PATH:
            if data.home_create:
                probe_home = os.path.join(home, data.username)
            else:
                probe_home = home

            pubkey_verrors = ValidationErrors()
            validate_sshpubkey_home_access(
                self,
                pubkey_verrors,
                "user_create",
                data.username,
                uid,
                group.gid,
                group_ids_to_gids(self, aux_groups),
                probe_home,
                data.home_mode,
                uid,
            )
            if pubkey_verrors:
                self._release_uid(uid)
                if group_created:
                    self.call_sync2(self.s.group.delete, group.id)
                pubkey_verrors.check()

        if home and home != DEFAULT_HOME_PATH:
            try:
                home = setup_homedir(
                    self,
                    home,
                    data.username,
                    data.home_mode,
                    uid,
                    group.gid,
                    data.home_create,
                )
            except Exception:
                # Homedir setup failed, we should remove any auto-generated group
                if group_created:
                    self.call_sync2(self.s.group.delete, group.id)

                self._release_uid(uid)

                raise

        row = {
            "uid": uid,
            "username": data.username,
            "home": home,
            "shell": data.shell,
            "full_name": data.full_name,
            "smb": data.smb,
            "userns_idmap": userns_idmap_to_db(data.userns_idmap),
            "password_disabled": data.password_disabled,
            "ssh_password_enabled": data.ssh_password_enabled,
            "locked": data.locked,
            "sudo_commands": data.sudo_commands,
            "sudo_commands_nopasswd": data.sudo_commands_nopasswd,
            "group": group.id,
            "email": data.email,
            "groups": webshare_membership(self, webshare=data.webshare, username=data.username, groups=aux_groups),
        }
        apply_password_update(row, password_update)

        pk = None  # Make sure pk exists to rollback in case of an error
        try:
            pk = self.middleware.call_sync("datastore.insert", "account.bsdusers", row, {"prefix": "bsdusr_"})
            self.middleware.call_sync(
                "datastore.insert",
                "account.twofactor_user_auth",
                {
                    "secret": None,
                    "user": pk,
                },
            )
        except Exception:
            if pk is not None:
                self.middleware.call_sync("datastore.delete", "account.bsdusers", pk)
            raise
        finally:
            self._release_uid(uid)

        self.call_sync2(self.s.service.control, "RELOAD", "ssh").wait_sync(raise_error=True)
        self.call_sync2(self.s.service.control, "RELOAD", "user").wait_sync(raise_error=True)

        if data.smb:
            self.middleware.call_sync("smb.update_passdb_user", row | {"id": pk})

        if os.path.isdir(SKEL_PATH) and os.path.exists(home) and home != DEFAULT_HOME_PATH:
            for f in os.listdir(SKEL_PATH):
                if f.startswith("dot"):
                    dest_file = os.path.join(home, f[3:])
                else:
                    dest_file = os.path.join(home, f)
                if not os.path.exists(dest_file):
                    shutil.copyfile(os.path.join(SKEL_PATH, f), dest_file)
                    chown_job = self.middleware.call_sync(
                        "filesystem.chown",
                        {
                            "path": dest_file,
                            "uid": uid,
                            "gid": group.gid,
                        },
                    )
                    chown_job.wait_sync()

            try:
                update_sshpubkey(self, home, {"uid": uid, "sshpubkey": data.sshpubkey}, group.group)
            except PermissionError as e:
                self.logger.warning("Failed to update authorized keys", exc_info=True)
                raise CallError(f"Failed to update authorized keys: {e}")

        return self._with_password(pk, password_update.password)

    def do_update(
        self,
        app: App | None,
        audit_callback: AuditCallback,
        id_: int,
        data: UserUpdate,
    ) -> UserCreateUpdateResult:
        if id_ > BASE_SYNTHETIC_DATASTORE_ID:
            audit_callback(self._directory_service_username(id_))
            raise CallError(
                "Users provided by a directory service must be modified through the identity provider "
                "(LDAP server or domain controller).",
                errno.EPERM,
            )

        entry = self.get_instance__sync(id_)
        audit_callback(entry.username)

        new = entry.updated(data)

        credentials = app.authenticated_credentials if app else None
        if credentials is not None and credentials.is_user_session:
            same_user_logged_in = entry.username == (self.middleware.call_sync("auth.me", app=app))["pw_name"]
        else:
            same_user_logged_in = False

        verrors = ValidationErrors()

        if supplied_flag(data, "password_disabled"):
            try:
                self.call_sync2(self.s.privilege.before_user_password_disable, entry)
            except CallError as e:
                verrors.add("user_update.password_disabled", e.errmsg)

        group: dict[str, Any]
        supplied_group = supplied(data, "group")
        if supplied_group is not undefined:
            if supplied_group is None:
                # sending `group` as None is okay in user.create since
                # it means, during user creation, a new primary group
                # will automatically be created for said user. However,
                # on update, a user MUST have a primary group. If someone
                # tries to send an explicit None value here, let's raise
                # an informative validation error.
                verrors.add("user_update.group", "User must have a primary group", errno.EINVAL)
                verrors.check()

            groups = self.middleware.call_sync("datastore.query", "account.bsdgroups", [("id", "=", supplied_group)])
            if not groups:
                verrors.add("user_update.group", f"Group {supplied_group} not found", errno.ENOENT)
                verrors.check()

            group = groups[0]
        else:
            group = entry.group
        verrors.check()

        if (
            same_user_logged_in
            and (self.middleware.call_sync("auth.twofactor.config"))["enabled"]
            and not entry.twofactor_auth_configured
            and not supplied_flag(data, "renew_twofactor_secret")
        ):
            verrors.add(
                "user_update.renew_twofactor_secret",
                "Two-factor authentication is enabled globally but not configured for this user.",
            )

        group_ids = [group["id"]]
        supplied_groups = supplied(data, "groups")
        if supplied_groups not in (undefined, None) and supplied_groups:
            group_ids.extend(supplied_groups)
        else:
            group_ids.extend(entry.groups)

        # NAS-136301: prevent locking all admin accounts
        if supplied(data, "locked") is True:
            number_admin_remaining = self.call_sync2(
                self.s.user.query,
                [
                    ["roles", "rin", "FULL_ADMIN"],
                    ["local", "=", True],
                    ["locked", "=", False],
                    ["id", "!=", entry.id],
                ],
                QueryOptions(count=True),
            )
            if 0 >= number_admin_remaining:
                verrors.add("user_update.locked", "After locking this user no local users will have FULL_ADMIN role")

        password_update = self.run_coroutine(common_validation(self, verrors, data, "user_update", group_ids, entry))

        try:
            st = os.stat(entry.home).st_mode
            old_mode = f"{stat.S_IMODE(st):03o}"
        except FileNotFoundError:
            old_mode = None

        supplied_home = supplied(data, "home")
        home = supplied_home if supplied_home not in (undefined, None) else entry.home
        had_home = entry.home != DEFAULT_HOME_PATH
        has_home = home != DEFAULT_HOME_PATH
        # root user and admin users are an exception to the rule
        if supplied_flag(data, "sshpubkey"):
            if not (entry.uid in [0, ADMIN_UID] or self.middleware.call_sync("filesystem.is_dataset_path", home)):
                verrors.add("user_update.sshpubkey", 'Home directory is not writable, leave this blank"')
            elif has_home:
                new_home = home
                if supplied_home is not undefined and supplied_flag(data, "home_create"):
                    new_home = os.path.join(home, new.username)

                validate_sshpubkey_home_access(
                    self,
                    verrors,
                    "user_update",
                    entry.username,
                    entry.uid,
                    group["bsdgrp_gid"],
                    group_ids_to_gids(self, group_ids),
                    new_home,
                    supplied_or_none(data, "home_mode"),
                    None,
                )

        # Do not allow attributes to be changed for builtin user
        if entry.immutable:
            if supplied(data, "home_mode") is not undefined:
                verrors.add("user_update.home_mode", "This attribute cannot be changed")

            immutable_now: dict[str, Any] = {
                "group": entry.group["id"],
                "home": entry.home,
                "username": entry.username,
                "smb": entry.smb,
                "userns_idmap": entry.userns_idmap,
            }
            for field, current in immutable_now.items():
                requested = supplied(data, field)
                if requested is not undefined and requested != current:
                    verrors.add(f"user_update.{field}", "This attribute cannot be changed")

        if not entry.smb and supplied_flag(data, "smb") and not password_update.password:
            # Changing from non-smb user to smb user requires re-entering password.
            verrors.add("user_update.smb", "Password must be reset in order to enable SMB authentication")

        verrors.check()

        must_change_pdb_entry = False
        for field, old_val in (("username", entry.username), ("password", None), ("locked", entry.locked)):
            new_val = password_update.password if field == "password" else supplied_or_none(data, field)
            if new_val is not None and old_val != new_val:
                if field == "username":
                    try:
                        self.middleware.call_sync("smb.remove_passdb_user", old_val, entry.sid)
                    except Exception:
                        self.logger.debug("Failed to remove passdb entry for user [%s]", old_val, exc_info=True)

                must_change_pdb_entry = True

        if entry.smb is True and supplied(data, "smb") is False:
            try:
                must_change_pdb_entry = False
                self.middleware.call_sync("smb.remove_passdb_user", entry.username, entry.sid)
            except Exception:
                self.logger.debug("Failed to remove passdb entry for user [%s]", entry.username, exc_info=True)

        if entry.smb is False and supplied(data, "smb") is True:
            must_change_pdb_entry = True

        # Copy the home directory if it changed
        home_old: str | None = None
        if has_home and supplied_home is not undefined:
            if supplied_flag(data, "home_create"):
                home = os.path.join(home, new.username)

            if had_home and entry.home != home:
                home_old = entry.home

        mode_to_set = supplied_or_none(data, "home_mode") or ("700" if old_mode is None else old_mode)

        # squelch any potential problems when this occurs
        if has_home:
            recreate_homedir_if_not_exists(
                self, {"home": home, "username": new.username, "uid": entry.uid}, group, mode_to_set
            )

        home_mode = None if entry.immutable else supplied_or_none(data, "home_mode")

        # The payload crosses to the standby as JSON, so it stays a plain dict.
        sshpubkey_user = {"uid": entry.uid, "sshpubkey": new.sshpubkey}
        try:
            update_sshpubkey_args = [
                home if home_old is None else home_old,
                sshpubkey_user,
                group["bsdgrp_group"],
            ]
            update_sshpubkey(self, *update_sshpubkey_args)
        except PermissionError as e:
            self.logger.warning("Failed to update authorized keys", exc_info=True)
            raise CallError(f"Failed to update authorized keys: {e}")
        else:
            if entry.uid in (0, ADMIN_UID):
                if self.middleware.call_sync("failover.licensed"):
                    try:
                        self.middleware.call_sync(
                            "failover.call_remote", "user.update_sshpubkey", update_sshpubkey_args
                        )
                    except Exception:
                        self.logger.error("Failed to sync root ssh pubkey to standby node", exc_info=True)

        if home_old is not None:
            # Background copy of user home directory to new path as the user in question.
            self.call_sync2(self.s.user.do_home_copy, home_old, home, new.username, home_mode, entry.uid)
        elif has_home and home_mode is not None:
            # A non-recursive call to set permissions should return almost immediately.
            perm_job = self.middleware.call_sync(
                "filesystem.setperm",
                {
                    "path": home,
                    "mode": home_mode,
                    "options": {"stripacl": True},
                },
            )
            perm_job.wait_sync()

        row = {
            "uid": new.uid,
            "username": new.username,
            "home": home,
            "shell": new.shell,
            "full_name": new.full_name,
            "builtin": new.builtin,
            "smb": new.smb,
            "userns_idmap": userns_idmap_to_db(new.userns_idmap),
            "password_disabled": new.password_disabled,
            "ssh_password_enabled": new.ssh_password_enabled,
            "locked": new.locked,
            "sudo_commands": new.sudo_commands,
            "sudo_commands_nopasswd": new.sudo_commands_nopasswd,
            "group": group["id"],
            "email": new.email,
            "groups": webshare_membership(self, webshare=new.webshare, username=new.username, groups=new.groups),
            "unixhash": entry.unixhash.get_secret_value(),
            "smbhash": entry.smbhash.get_secret_value(),
            "last_password_change": (
                None if entry.last_password_change is None else int(entry.last_password_change.timestamp())
            ),
            "password_history": " ".join(entry.password_history.get_secret_value() or []),
        }
        apply_password_update(row, password_update)

        self.middleware.call_sync("datastore.update", "account.bsdusers", id_, row, {"prefix": "bsdusr_"})

        reset_tally(new.username)
        self.call_sync2(self.s.service.control, "RELOAD", "ssh").wait_sync(raise_error=True)
        self.call_sync2(self.s.service.control, "RELOAD", "user").wait_sync(raise_error=True)
        if new.smb and must_change_pdb_entry:
            self.middleware.call_sync("smb.update_passdb_user", row | {"id": id_})

        return self._with_password(id_, password_update.password)

    def do_delete(
        self,
        app: App | None,
        audit_callback: AuditCallback,
        id_: int,
        options: UserDeleteOptions,
    ) -> int:
        if id_ > BASE_SYNTHETIC_DATASTORE_ID:
            audit_callback(self._directory_service_username(id_))
            raise CallError(
                "Users provided by a directory service must be deleted from the identity provider "
                "(LDAP server or domain controller).",
                errno.EPERM,
            )

        entry = self.get_instance__sync(id_)
        audit_callback(entry.username)

        credentials = app.authenticated_credentials if app else None
        if (
            credentials is not None and credentials.is_user_session and entry.username == credentials.user["username"]  # type: ignore[attr-defined]
        ):
            raise CallError("Cannot delete the currently active user", errno.EINVAL)

        if entry.builtin:
            raise CallError("Cannot delete a built-in user", errno.EINVAL)

        if entry.immutable:
            raise CallError("Cannot delete an immutable user", errno.EINVAL)

        self.call_sync2(self.s.privilege.before_user_delete, entry)

        if options.delete_group and not entry.group["bsdgrp_builtin"]:
            count = self.middleware.call_sync(
                "datastore.query",
                "account.bsdgroupmembership",
                [("group", "=", entry.group["id"])],
                {"prefix": "bsdgrpmember_", "count": True},
            )
            count2 = self.middleware.call_sync(
                "datastore.query",
                "account.bsdusers",
                [("group", "=", entry.group["id"]), ("id", "!=", id_)],
                {"prefix": "bsdusr_", "count": True},
            )
            if count == 0 and count2 == 0:
                try:
                    self.call_sync2(self.s.group.delete, entry.group["id"])
                except Exception:
                    self.logger.warning("Failed to delete primary group of %s", entry.username, exc_info=True)

        if entry.home and entry.home != DEFAULT_HOME_PATH:
            try:
                shutil.rmtree(os.path.join(entry.home, ".ssh"))
            except Exception:
                pass

        if entry.smb:
            self.middleware.call_sync("smb.remove_passdb_user", entry.username, entry.sid)

        # TODO: add a hook in CIFS service
        cifs = self.middleware.call_sync("datastore.query", "services.cifs", [], {"prefix": "cifs_srv_"})
        if cifs:
            if cifs[0]["guest"] == entry.username:
                self.middleware.call_sync(
                    "datastore.update",
                    "services.cifs",
                    cifs[0]["id"],
                    {"guest": "nobody"},
                    {"prefix": "cifs_srv_"},
                )

        if attributes := self.middleware.call_sync(
            "datastore.query", "account.bsdusers_webui_attribute", [["uid", "=", entry.uid]]
        ):
            self.middleware.call_sync("datastore.delete", "account.bsdusers_webui_attribute", attributes[0]["id"])

        self.middleware.call_sync("datastore.delete", "account.bsdusers", id_)
        self.call_sync2(self.s.service.control, "RELOAD", "ssh").wait_sync(raise_error=True)
        reset_tally(entry.username)
        self.call_sync2(self.s.service.control, "RELOAD", "user").wait_sync(raise_error=True)
        try:
            self.middleware.call_sync(
                "idmap.gencache.del_idmap_cache_entry",
                {
                    "entry_type": "UID2SID",
                    "entry": entry.uid,
                },
            )
        except MatchNotFound:
            pass

        return id_

    def _with_password(self, id_: int, password: str | None) -> UserCreateUpdateResult:
        entry = self.get_instance__sync(id_)
        return UserCreateUpdateResult(**entry.model_dump(expose_secrets=True), password=password)

    def _directory_service_username(self, id_: int) -> str:
        # datastore ids for directory services are created by adding the
        # posix ID to a base value so that we can use getpwuid / getgrgid to
        # convert back to a username / group name
        try:
            user_obj = self.call_sync2(
                self.s.user.get_user_obj,
                UserGetUserObj(uid=id_ - BASE_SYNTHETIC_DATASTORE_ID),
            )
        except KeyError:
            return "UNKNOWN"

        return user_obj.pw_name
