from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import errno
import os
from pathlib import Path
import stat
from typing import TYPE_CHECKING, Any

from pydantic import Secret

from middlewared.api.current import UserCreate, UserEntry, UserGetUserObj, UserUpdate
from middlewared.async_validators import check_path_resides_within_volume
from middlewared.plugins.idmap_.idmap_constants import BASE_SYNTHETIC_DATASTORE_ID
from middlewared.service import ValidationErrors
from middlewared.utils.crypto import generate_string
from middlewared.utils.lang import undefined
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
    "supplied",
    "supplied_flag",
    "supplied_or_none",
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


def supplied(data: UserCreate | UserUpdate, field: str) -> Any:
    """What `data` says about `field`: its value, or `undefined` when it says nothing.

    An update payload leaves every unsupplied field as `undefined`, and `bool(undefined)`
    is `True`, so callers must compare against `undefined` rather than test truthiness.
    `Secret` values are unwrapped so callers see the cleartext they are validating.
    """
    value = getattr(data, field, undefined)
    return value.get_secret_value() if isinstance(value, Secret) else value


def supplied_flag(data: UserCreate | UserUpdate, field: str) -> bool:
    """`data`'s boolean for `field`, `False` when it says nothing about it."""
    value = supplied(data, field)
    return value is not undefined and bool(value)


def supplied_or_none(data: UserCreate | UserUpdate, field: str) -> Any:
    """`data`'s value for `field`, `None` when it says nothing about it.

    For fields where "not supplied" and "no value" mean the same thing downstream.
    """
    value = supplied(data, field)
    return None if value is undefined else value


def _effective(data: UserCreate | UserUpdate, old: UserEntry | None, field: str) -> Any:
    """The value the account ends up with for `field` once `data` is applied over `old`."""
    value = supplied(data, field)
    if value is not undefined:
        return value

    return getattr(old, field, undefined) if old is not None else undefined


async def _resolve_password(
    context: ServiceContext,
    verrors: ValidationErrors,
    data: UserCreate | UserUpdate,
    schema: str,
    old: UserEntry | None,
) -> PasswordUpdate:
    """Validate the payload's password and work out the columns that go with it."""
    requested = supplied(data, "password")
    result = PasswordUpdate(
        set_hashes=requested is not undefined,
        password=None if requested is undefined else requested,
    )
    changed = False

    if supplied_flag(data, "random_password"):
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
    data: UserCreate | UserUpdate,
    schema: str,
    group_ids: list[int],
    old: UserEntry | None = None,
) -> PasswordUpdate:
    """Validate a create (`old` is `None`) or update payload, and resolve its password columns.

    The password columns cannot be carried on `data`: they are `Excluded` fields, which
    `model_dump` drops unconditionally, so they are reported back to the caller instead.
    """
    exclude_filter = [("id", "!=", old.id)] if old else []

    users = await context.middleware.call(
        "datastore.query",
        "account.bsdusers",
        exclude_filter,
        {"prefix": "bsdusr_"},
    )

    username = supplied(data, "username")
    uid = supplied(data, "uid")
    userns_idmap = supplied(data, "userns_idmap")
    home = supplied(data, "home")
    home_mode = supplied(data, "home_mode")
    shell = supplied(data, "shell")
    groups = supplied(data, "groups")
    full_name = supplied(data, "full_name")
    sudo_commands = supplied(data, "sudo_commands")
    sudo_commands_nopasswd = supplied(data, "sudo_commands_nopasswd")

    # Privileged-roles conflict can be introduced by either changing userns_idmap or
    # changing the user's group membership, so the check needs to run on both paths.
    touches_membership = any(supplied(data, field) is not undefined for field in ("userns_idmap", "group", "groups"))
    if _effective(data, old, "userns_idmap") not in (None, undefined) and touches_membership:
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

    if userns_idmap is not undefined and userns_idmap:
        if old and old.builtin:
            verrors.add(
                f"{schema}.userns_idmap",
                "User namespace idmaps may not be configured for builtin accounts.",
            )

        effective_uid = _effective(data, old, "uid")
        await validate_userns_idmap_conflict(
            context,
            verrors,
            schema,
            userns_idmap,
            None if effective_uid is undefined else effective_uid,
            exclude_id=old.id if old else None,
        )

    password_update = await _resolve_password(context, verrors, data, schema, old)

    if uid is not undefined and uid is not None:
        try:
            existing_user = await context.call2(context.s.user.get_user_obj, UserGetUserObj(uid=uid))
        except KeyError:
            pass
        else:
            verrors.add(
                f"{schema}.uid",
                f"Uid {uid} is already used (user {existing_user.pw_name} has it)",
                errno.EEXIST,
            )

    if username is not undefined:
        if any(u["username"] == username for u in users):
            verrors.add(
                f"{schema}.username",
                f'The username "{username}" already exists.',
                errno.EEXIST,
            )

        if supplied_flag(data, "smb"):
            if any(u["smb"] and u["username"].casefold() == username.casefold() for u in users):
                verrors.add(
                    f"{schema}.smb",
                    f'Username "{username}" conflicts with existing SMB user. Note that SMB '
                    "usernames are case-insensitive.",
                    errno.EEXIST,
                )

    stig_enabled = (await context.call2(context.s.system.security.config)).enable_gpos_stig

    if _effective(data, old, "smb"):
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

        if _effective(data, old, "password_disabled"):
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
                not _effective(data, old, "password_disabled"),
                not _effective(data, old, "locked"),
                old.unixhash.get_secret_value() != "*",
            ]
        )

        if stig_enabled and is_enabled_system_account:
            verrors.add(
                f"{schema}.immutable",
                f"{_effective(data, old, 'username')} is a System Administrator account and is not permitted to be "
                "enabled for password authentication when General Purpose OS STIG compatibility is enabled. "
                "Please disable the password or lock the account.",
            )

    if not old and not password_update.password and not supplied_flag(data, "password_disabled"):
        verrors.add(f"{schema}.password", "Password is required")
    elif supplied_flag(data, "password_disabled") and password_update.password:
        verrors.add(
            f"{schema}.password_disabled",
            'Leave "Password" blank when "Disable password login" is checked.',
        )

    if home is not undefined:
        home_create = supplied_flag(data, "home_create")
        if await context.to_thread(validate_homedir_path, context, verrors, schema, home, home_create, users):
            await check_path_resides_within_volume(verrors, context.middleware, schema, home)
            await check_path_service_write_allowed(verrors, context.middleware, f"{schema}.home", home)
        elif _effective(data, old, "ssh_password_enabled"):
            verrors.add(f"{schema}.home", "SSH password login requires a valid home path.")

    if home_mode is not undefined:
        try:
            o = int(home_mode, 8)
            assert o & 0o777 == o
            if o & (stat.S_IRUSR) == 0:
                verrors.add(f"{schema}.home_mode", "Home directory must be readable by User.")
            if o & (stat.S_IXUSR) == 0:
                verrors.add(f"{schema}.home_mode", "Home directory must be executable by User.")
        except (AssertionError, ValueError, TypeError):
            verrors.add(f"{schema}.home_mode", "Please provide a valid value for home_mode attribute")

    if groups is not undefined:
        new_groups = groups or []
        if new_groups and len(new_groups) > 64:
            verrors.add(f"{schema}.groups", "A user cannot belong to more than 64 auxiliary groups.")

        existing_groups = {g["id"]: g for g in await context.middleware.call("datastore.query", "account_bsdgroups")}

        for idx, dbid in enumerate(new_groups):
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
    if old and old.uid == 0:  # Root user being updated
        # root user is not allowed access via webshare
        if supplied_flag(data, "webshare"):
            verrors.add(f"{schema}.webshare", "The root user is not allowed access via webshare.")

        if groups is not undefined:
            # Get builtin_administrators group primary key (datastore id)
            builtin_admin_group = await context.middleware.call(
                "datastore.query",
                "account.bsdgroups",
                [("group", "=", "builtin_administrators")],
                {"get": True, "prefix": "bsdgrp_"},
            )
            builtin_admin_pk = builtin_admin_group["id"]

            # Rule 1: Cannot remove root from builtin_administrators
            if builtin_admin_pk not in new_groups:
                verrors.add(
                    f"{schema}.groups",
                    "The root user must remain a member of the builtin_administrators group.",
                )

            # Rule 2: Root can only be in builtin_administrators, no other groups
            if new_groups != [builtin_admin_pk]:
                verrors.add(
                    f"{schema}.groups",
                    "The root user may only be a member of the builtin_administrators group.",
                )

    if full_name is not undefined:
        for illegal_char in filter(lambda c: c in full_name, (":", "\n")):
            verrors.add(f"{schema}.full_name", f"The {illegal_char!r} character is not allowed.")

    if shell is not undefined:
        if shell not in await context.call2(context.s.user.shell_choices, group_ids):
            verrors.add(f"{schema}.shell", "Please select a valid shell.")
        elif _effective(data, old, "ssh_password_enabled") and shell == NO_LOGIN_SHELL:
            verrors.add(f"{schema}.shell", "SSH password login requires a login shell.")

    if sudo_commands is not undefined:
        verrors.add_child(
            f"{schema}.sudo_commands",
            await context.to_thread(validate_sudo_commands, sudo_commands),
        )

    if sudo_commands_nopasswd is not undefined:
        verrors.add_child(
            f"{schema}.sudo_commands_nopasswd",
            await context.to_thread(validate_sudo_commands, sudo_commands_nopasswd),
        )

    if supplied_flag(data, "ssh_password_enabled"):
        two_factor_config = await context.middleware.call("auth.twofactor.config")
        if two_factor_config["enabled"] and two_factor_config["services"]["ssh"]:
            error = "2FA for this user needs to be explicitly configured before password based SSH access is enabled."
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

        if _effective(data, old, "home") == DEFAULT_HOME_PATH or _effective(data, old, "shell") == NO_LOGIN_SHELL:
            verrors.add(
                f"{schema}.ssh_password_enabled",
                "Cannot be enabled without a valid home path and login shell.",
            )

    return password_update
