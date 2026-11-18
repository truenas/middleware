from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import errno
import os
from pathlib import Path
import stat
from typing import TYPE_CHECKING, Any

from middlewared.api.current import UserCreate, UserEntry, UserGetUserObj, UserUpdate
from middlewared.async_validators import check_path_resides_within_volume
from middlewared.plugins.idmap_.idmap_constants import BASE_SYNTHETIC_DATASTORE_ID
from middlewared.service import ValidationErrors
from middlewared.utils.crypto import generate_string
from middlewared.utils.security import MAX_PASSWORD_HISTORY
from middlewared.utils.service.path import check_path_service_write_allowed
from middlewared.utils.time_utils import utc_now

from .constants import ALLOWED_BUILTIN_GIDS, DEFAULT_HOME_PATH, NO_LOGIN_SHELL
from .password import password_security_validate
from .utils import validate_sudo_commands

if TYPE_CHECKING:
    from middlewared.service import ServiceContext

__all__ = (
    "PasswordUpdate",
    "common_validation",
    "validate_homedir_path",
    "validate_sshpubkey_home_access",
    "validate_userns_idmap_conflict",
)


@dataclass(slots=True)
class PasswordUpdate:
    """What a create or update must write to the password-related columns.

    These cannot be reported on the payload model itself: `last_password_change` and
    `password_history` are `Excluded` fields, and `model_dump` drops those unconditionally.

    `set_hashes` is `False` when the payload said nothing about the password, in which case
    the stored hashes must be left alone. Otherwise `password` is the cleartext to hash --
    the caller's, or a generated one when `random_password` was asked for -- and `None`
    there means the hashes are reset to the "no password" marker.

    `last_password_change` and `password_history` accompany an actual password change and
    stay `None` when there is none.
    """

    set_hashes: bool = False
    password: str | None = None
    last_password_change: datetime | None = None
    password_history: list[str] | None = None


async def _resolve_password(
    context: ServiceContext,
    verrors: ValidationErrors,
    operation: UserCreate | UserUpdate,
    schema: str,
    old: UserEntry | None,
) -> PasswordUpdate:
    """Validate the payload's password and work out the columns that go with it.

    An update that omits `password` means "keep the stored hashes".
    """
    result = PasswordUpdate()
    if old is None or "password" in operation.model_fields_set:
        result.set_hashes = True
        result.password = operation.password.get_secret_value()
    changed = False

    if operation.random_password is True:
        if result.password:
            verrors.add(
                f"{schema}.random_password",
                "Requesting a randomized password while simultaneously supplying "
                "an explicit password is not permitted.",
            )
        else:
            result.password = generate_string(string_size=20)
            result.set_hashes = True
            changed = True

    elif result.password:
        if old is None:
            history = None
        else:
            history = (old.password_history.get_secret_value() or []) + [old.unixhash.get_secret_value()]

        await password_security_validate(context, schema, verrors, result.password, history)
        changed = True

    if changed:
        result.last_password_change = utc_now(naive=False)

        if old is not None:
            # We store a number of hashes equal to the maximum possible value
            # of the password history parameter so that admins can bump the
            # history value up and have it take actual effect.
            password_history = list(old.password_history.get_secret_value() or [])
            password_history.append(old.unixhash.get_secret_value())
            while len(password_history) > MAX_PASSWORD_HISTORY:
                password_history.pop(0)

            result.password_history = password_history

    return result


def validate_homedir_mountinfo(
    context: ServiceContext,
    verrors: ValidationErrors,
    schema: str,
    home_path: Path,
) -> bool:
    sfs = context.middleware.call_sync("filesystem.statfs", home_path.as_posix())
    if "RO" in sfs.flags:
        verrors.add(f"{schema}.home", "Path has the ZFS readonly property set.")
        return False

    if sfs.fstype != "zfs":
        verrors.add(f"{schema}.home", "Path is not on a ZFS filesystem")
        return False

    return True


def validate_homedir_path(
    context: ServiceContext,
    verrors: ValidationErrors,
    schema: str,
    home: str,
    home_create: bool,
    users: list[dict[str, Any]],
) -> bool:
    p = Path(home)

    if not p.is_absolute():
        verrors.add(f"{schema}.home", '"Home Directory" must be an absolute path.')
        return False

    if p.is_file():
        verrors.add(f"{schema}.home", '"Home Directory" cannot be a file.')
        return False

    if ":" in home:
        verrors.add(f"{schema}.home", '"Home Directory" cannot contain colons (:).')
        return False

    if home == DEFAULT_HOME_PATH:
        return False

    if not p.exists():
        if home_create:
            verrors.add(
                f"{schema}.home",
                f"{home}: path specified to use for home directory creation does not "
                "exist. TrueNAS uses the provided path as the parent directory of the "
                "newly-created home directory.",
            )

        else:
            verrors.add(
                f"{schema}.home",
                f"{home}: path specified to use as home directory does not exist.",
            )

        if not p.parent.exists():
            verrors.add(
                f"{schema}.home",
                f"{p.parent}: parent path of specified home directory does not exist.",
            )

    elif validate_homedir_mountinfo(context, verrors, schema, p):
        attrs = context.middleware.call_sync("filesystem.stat", home).attributes
        if "IMMUTABLE" in attrs:
            verrors.add(f"{schema}.home", f"{home}: home directory path is immutable.")

    in_use = next((u for u in users if u["home"] == home), None)
    if in_use:
        verrors.add(
            f"{schema}.home",
            f"{home}: homedir already used by {in_use['username']}.",
            errno.EEXIST,
        )

    if not home.startswith("/mnt"):
        verrors.add(
            f"{schema}.home",
            f'"Home Directory" must begin with /mnt or set to {DEFAULT_HOME_PATH}.',
        )
    elif home in ("/mnt", "/mnt/"):
        verrors.add(f"{schema}.home", '"Home Directory" cannot be at root of "/mnt"')

    if verrors:
        # if we're already going to error out, skip more expensive tests
        return False

    if not any(
        home == i["path"] or home.startswith(i["path"] + "/") for i in context.middleware.call_sync("pool.query")
    ):
        verrors.add(
            f"{schema}.home",
            f'The path for the home directory "({home})" must include a volume or dataset.',
        )
    elif context.call_sync2(context.s.zfs.resource.path_is_locked, home):
        verrors.add(
            f"{schema}.home",
            'Path component for "Home Directory" is currently encrypted and locked',
        )
    elif len(p.resolve().parents) == 2 and not home_create:
        verrors.add(
            f"{schema}.home",
            f'The specified path is a ZFS pool mountpoint "({home})".',
        )

    return p.exists() and not verrors


def validate_sshpubkey_home_access(
    context: ServiceContext,
    verrors: ValidationErrors,
    schema: str,
    username: str,
    uid: int,
    gid: int,
    groups: list[int],
    home: str,
    new_mode: str | None,
    new_owner_uid: int | None,
) -> None:
    """Verify that sshd will be able to read `home`/.ssh/authorized_keys.

    `username`, `uid`, `gid` and `groups` describe the account as it will exist once the operation completes.

    `new_mode` and `new_owner_uid` are the mode and the owner that the home directory will be given by this
    operation, or None when it is left as it is.
    """

    if new_mode is not None:
        probe_path = os.path.dirname(home)
    else:
        probe_path = home

    access_errors = context.middleware.call_sync(
        "filesystem.can_access_as_cred_errors",
        {"pw_name": username, "pw_uid": uid, "pw_gid": gid, "grouplist": groups},
        probe_path,
        ["EXECUTE"],
        False,
        True,
    )
    if access_errors:
        # access_errors[0] is the shallowest component of the path that the credential cannot use.
        component = access_errors[0].failing_component.decode()
        try:
            st = os.stat(component)
            details = f"it is mode {stat.S_IMODE(st.st_mode):03o}, owned by uid {st.st_uid} and gid {st.st_gid}"
        except OSError:
            details = os.strerror(access_errors[0].errnum)

        verrors.add(
            f"{schema}.sshpubkey",
            f"User {username!r} is not allowed to access {component!r} ({details}). OpenSSH will reject the public "
            f"key. Please set permissions that allow the user to traverse every directory leading to {home!r}.",
        )
        return

    mode: int | None
    if new_mode is not None:
        mode = int(new_mode, 8)
    else:
        mode = None
    owner_uid = new_owner_uid
    if mode is None or owner_uid is None:
        try:
            st = os.stat(home)
        except FileNotFoundError:
            # The home directory is created as part of this operation, so its `owner_uid` and `mode` are already
            # correct.
            pass
        else:
            if mode is None:
                mode = stat.S_IMODE(st.st_mode)
            if owner_uid is None:
                owner_uid = st.st_uid

    if owner_uid is not None and owner_uid not in (0, uid):
        verrors.add(
            f"{schema}.sshpubkey",
            f"Home directory {home!r} is owned by uid {owner_uid}, which is neither the user nor root. OpenSSH "
            "will reject the public key. Please set correct home directory ownership.",
        )

    if mode is not None and mode & 0o002:
        verrors.add(
            f"{schema}.sshpubkey",
            f"Home directory {home!r} is world-writable (mode {mode:03o}). OpenSSH will reject the public key. "
            "Please set correct home directory permissions.",
        )


async def validate_userns_idmap_conflict(
    context: ServiceContext,
    verrors: ValidationErrors,
    schema: str,
    userns_idmap: str | int | None,
    uid: int | None,
    exclude_id: int | None = None,
) -> None:
    """Verify the proposed userns_idmap doesn't collide with another local user's mapping.

    `uid` is the user's host UID; it may be None during creation if not yet auto-assigned,
    in which case a DIRECT mapping cannot be resolved and the check is deferred. Callers
    that auto-assign the UID must re-invoke this check after assignment.
    """
    if not userns_idmap:
        return

    proposed = uid if userns_idmap == "DIRECT" else userns_idmap
    if proposed is None:
        return

    conflict_filters: list[Any] = [
        ["local", "=", True],
        ["userns_idmap", "nin", [None, 0]],
    ]
    if exclude_id is not None:
        conflict_filters.append(["id", "!=", exclude_id])

    for other in await context.call2(context.s.user.query, conflict_filters):
        other_target = other.uid if other.userns_idmap == "DIRECT" else other.userns_idmap
        if other_target == proposed:
            verrors.add(
                f"{schema}.userns_idmap",
                f"User {other.username!r} already maps to container UID {proposed}.",
            )
            return


async def common_validation(
    context: ServiceContext,
    verrors: ValidationErrors,
    new: UserCreate | UserEntry,
    operation: UserCreate | UserUpdate,
    schema: str,
    group_ids: list[int],
    old: UserEntry | None = None,
) -> PasswordUpdate:
    """Validate a create (`old` is `None`) or update, and resolve its password columns.

    `new` is the account as it will exist once the operation completes: `operation` itself on create,
    `old.updated(operation)` on update. `operation` is only consulted for what is not stored on the account
    (`password`, `random_password`, `home_create`, `home_mode`), for whether `shell` was sent, and for whether
    the request itself disables password login.

    The password columns cannot be carried on `operation`: they are `Excluded` fields, which
    `model_dump` drops unconditionally, so they are reported back to the caller instead.
    """
    exclude_filter = [("id", "!=", old.id)] if old else []

    users = await context.middleware.call(
        "datastore.query",
        "account.bsdusers",
        exclude_filter,
        {"prefix": "bsdusr_"},
    )

    # A check is re-run when a field it reads changes, not on every request: stored state may predate a rule
    # (or drift, like a sudo command whose binary is gone) and must not block unrelated edits.
    membership_changed = old is None or group_ids != [old.group["id"], *old.groups]
    groups_changed = old is None or new.groups != old.groups

    if new.userns_idmap is not None:
        idmap_changed = old is None or new.userns_idmap != old.userns_idmap
        if idmap_changed or membership_changed:
            if await context.call2(
                context.s.group.query,
                [
                    ["local", "=", True],
                    ["roles", "!=", []],
                    ["id", "in", group_ids],
                ],
            ):
                verrors.add(
                    f"{schema}.userns_idmap",
                    "User namespace idmaps may not be configured for privileged accounts.",
                )

        if idmap_changed:
            # Builtin accounts keep the idmap they ship with (e.g. `apps`); they may not be given a new one.
            if old and old.builtin:
                verrors.add(
                    f"{schema}.userns_idmap",
                    "User namespace idmaps may not be configured for builtin accounts.",
                )

            await validate_userns_idmap_conflict(
                context,
                verrors,
                schema,
                new.userns_idmap,
                new.uid,
                exclude_id=old.id if old else None,
            )

    password_update = await _resolve_password(context, verrors, operation, schema, old)

    # `uid` cannot be changed by an update, so only a uid requested on create is checked.
    if old is None and new.uid is not None:
        try:
            existing_user = await context.call2(context.s.user.get_user_obj, UserGetUserObj(uid=new.uid))
        except KeyError:
            pass
        else:
            verrors.add(
                f"{schema}.uid",
                f"Uid {new.uid} is already used (user {existing_user.pw_name} has it)",
                errno.EEXIST,
            )

    if any(u["username"] == new.username for u in users):
        verrors.add(
            f"{schema}.username",
            f'The username "{new.username}" already exists.',
            errno.EEXIST,
        )

    if new.smb and any(u["smb"] and u["username"].casefold() == new.username.casefold() for u in users):
        verrors.add(
            f"{schema}.smb",
            f'Username "{new.username}" conflicts with existing SMB user. Note that SMB '
            "usernames are case-insensitive.",
            errno.EEXIST,
        )

    stig_enabled = (await context.call2(context.s.system.security.config)).enable_gpos_stig

    if new.smb:
        if not await context.middleware.call("smb.is_configured"):
            if (await context.middleware.call("systemdataset.sysdataset_path")) is None:
                verrors.add(
                    f"{schema}.smb",
                    "System dataset is not mounted at expected path. This may indicate "
                    "an underlying issue with the pool hosting the system dataset. "
                    "SMB users may not be configured until this configuration issue is addressed.",
                )
            else:
                verrors.add(
                    f"{schema}.smb",
                    "SMB users may not be configured while SMB service backend is unitialized.",
                )

        if new.password_disabled:
            verrors.add(f"{schema}.password_disabled", "Password authentication may not be disabled for SMB users.")

        if stig_enabled:
            verrors.add(
                f"{schema}.smb",
                "SMB authentication for local user accounts is not permitted when General Purpose OS "
                "STIG compatibility is enabled.",
            )

    if old:
        is_enabled_system_account = old.immutable and any(
            [
                not new.password_disabled,
                not new.locked,
                old.unixhash.get_secret_value() != "*",
            ]
        )

        if stig_enabled and is_enabled_system_account:
            verrors.add(
                f"{schema}.immutable",
                f"{new.username} is a System Administrator account and is not permitted to be "
                "enabled for password authentication when General Purpose OS STIG compatibility is enabled. "
                "Please disable the password or lock the account.",
            )

    # Only a request that itself disables password login contradicts the password sent with it. A stored
    # `password_disabled` leaves the password dormant rather than forbidden, so it may still be rotated.
    if operation.password_disabled is True and password_update.password:
        verrors.add(
            f"{schema}.password_disabled",
            'Leave "Password" blank when "Disable password login" is checked.',
        )
    elif old is None and not password_update.password and not new.password_disabled:
        verrors.add(f"{schema}.password", "Password is required")

    if old is None or new.home != old.home or operation.home_create is True:
        home_create = operation.home_create is True
        if await context.to_thread(validate_homedir_path, context, verrors, schema, new.home, home_create, users):
            await check_path_resides_within_volume(verrors, context.middleware, schema, new.home)
            await check_path_service_write_allowed(
                verrors, context.middleware, f"{schema}.home", new.home, beneath=True
            )
        elif new.ssh_password_enabled:
            verrors.add(f"{schema}.home", "SSH password login requires a valid home path.")

    # `home_mode` is not stored on the account, so on update there is only something to check if it was sent.
    if old is None or "home_mode" in operation.model_fields_set:
        try:
            o = int(operation.home_mode, 8)
            assert o & 0o777 == o
            if o & (stat.S_IRUSR) == 0:
                verrors.add(f"{schema}.home_mode", "Home directory must be readable by User.")
            if o & (stat.S_IXUSR) == 0:
                verrors.add(f"{schema}.home_mode", "Home directory must be executable by User.")
        except (AssertionError, ValueError, TypeError):
            verrors.add(f"{schema}.home_mode", "Please provide a valid value for home_mode attribute")

    if groups_changed:
        if len(new.groups) > 64:
            verrors.add(f"{schema}.groups", "A user cannot belong to more than 64 auxiliary groups.")

        existing_groups = {
            g["id"]: g for g in await context.middleware.call("datastore.query", "account_bsdgroups")
        }

        for idx, dbid in enumerate(new.groups):
            if dbid not in existing_groups:
                verrors.add(f"{schema}.groups.{idx}", "This group does not exist.")

            if dbid >= BASE_SYNTHETIC_DATASTORE_ID:
                verrors.add(
                    f"{schema}.groups.{idx}",
                    "Local users may not be members of directory services groups.",
                )

            entry = existing_groups.get(dbid)
            if entry and entry["bsdgrp_builtin"] and entry["bsdgrp_gid"] not in ALLOWED_BUILTIN_GIDS:
                if not old or dbid not in old.groups:
                    verrors.add(
                        f"{schema}.groups.{idx}",
                        f"{entry['bsdgrp_group']}: membership of this builtin group may not be altered.",
                    )

    # Root user restrictions
    if old and old.uid == 0:
        if new.webshare and not old.webshare:
            verrors.add(f"{schema}.webshare", "The root user is not allowed access via webshare.")

        if groups_changed:
            builtin_admin_group = await context.middleware.call(
                "datastore.query",
                "account.bsdgroups",
                [("group", "=", "builtin_administrators")],
                {"get": True, "prefix": "bsdgrp_"},
            )
            if builtin_admin_group["id"] not in new.groups:
                verrors.add(
                    f"{schema}.groups",
                    "The root user must remain a member of the builtin_administrators group.",
                )

            if new.groups != [builtin_admin_group["id"]]:
                verrors.add(
                    f"{schema}.groups",
                    "The root user may only be a member of the builtin_administrators group.",
                )

    for illegal_char in filter(lambda c: c in new.full_name, (":", "\n")):
        verrors.add(f"{schema}.full_name", f"The {illegal_char!r} character is not allowed.")

    # Builtin accounts are allowed to preserve their invalid shell: they ship with shells such as /bin/false or
    # /bin/sync that are not offered as choices. Any other shell is checked when it is sent or when the groups
    # change, because the TrueNAS CLI shells are offered to privileged accounts only.
    if "shell" in operation.model_fields_set or membership_changed:
        if new.shell not in await context.call2(context.s.user.shell_choices, group_ids):
            if old is None or not old.builtin or new.shell != old.shell:
                verrors.add(f"{schema}.shell", "Please select a valid shell.")
        elif new.ssh_password_enabled and new.shell == NO_LOGIN_SHELL:
            verrors.add(f"{schema}.shell", "SSH password login requires a login shell.")

    if old is None or new.sudo_commands != old.sudo_commands:
        verrors.add_child(
            f"{schema}.sudo_commands",
            await context.to_thread(validate_sudo_commands, new.sudo_commands),
        )
    if old is None or new.sudo_commands_nopasswd != old.sudo_commands_nopasswd:
        verrors.add_child(
            f"{schema}.sudo_commands_nopasswd",
            await context.to_thread(validate_sudo_commands, new.sudo_commands_nopasswd),
        )

    # Both requirements gate turning SSH password login on: an account that already has it keeps working, and a
    # later change of its home or shell is caught by the `home` and `shell` checks above.
    if new.ssh_password_enabled and (old is None or not old.ssh_password_enabled):
        two_factor_config = await context.middleware.call("auth.twofactor.config")
        if two_factor_config["enabled"] and two_factor_config["services"]["ssh"]:
            error = (
                "2FA for this user needs to be explicitly configured before password based SSH access is enabled."
            )
            if old is None:
                verrors.add(
                    f"{schema}.ssh_password_enabled",
                    error + " User will be created with SSH password access disabled and after 2FA has been "
                    "configured for this user, SSH password access can be enabled.",
                )
            else:
                translated = await context.call2(context.s.user.translate_username, old.username)
                if translated.twofactor_auth_configured is False:
                    verrors.add(f"{schema}.ssh_password_enabled", error)

        if new.home == DEFAULT_HOME_PATH or new.shell == NO_LOGIN_SHELL:
            verrors.add(
                f"{schema}.ssh_password_enabled",
                "Cannot be enabled without a valid home path and login shell.",
            )

    return password_update
