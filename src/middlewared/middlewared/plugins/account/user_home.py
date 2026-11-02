from __future__ import annotations

from contextlib import suppress
from dataclasses import asdict
import errno
import os
import shutil
import stat
from typing import TYPE_CHECKING, Any

from truenas_os_pyutils.io import atomic_write
from truenas_os_pyutils.truenas_shutil import CopyTreeConfig, CopyTreeStats, copytree

from middlewared.api.current import (
    FilesystemMkdirData,
    FilesystemMkdirOptions,
    GroupGetGroupObj,
)
from middlewared.service import CallError

from .constants import DEFAULT_HOME_PATH

if TYPE_CHECKING:
    from middlewared.job import Job
    from middlewared.service import ServiceContext

__all__ = (
    "do_home_copy",
    "read_authorized_keys",
    "recreate_homedir_if_not_exists",
    "setup_homedir",
    "update_sshpubkey",
)


def read_authorized_keys(context: ServiceContext, homedir: str) -> str | None:
    # Extravagant zpool / hardware errors may manifest as IO errors during filesystem operations (even though the
    # pool itself imports). Since this is a hot codepath in the `extend` method (which *must not* fail) we
    # suppress the IOError here, and allow other filesystem operations to complain loudly at the user.
    with suppress(FileNotFoundError, IOError):
        with open(f"{homedir}/.ssh/authorized_keys") as f:
            try:
                return f.read().strip()
            except UnicodeDecodeError:
                context.logger.warning("Invalid encoding detected in authorized_keys file")

    return None


def setup_homedir(
    context: ServiceContext,
    path: str,
    username: str,
    mode: str,
    uid: int,
    gid: int,
    create: bool = False,
) -> str:
    homedir_created = False

    if create:
        target = os.path.join(path, username)
        try:
            # We do not raise exception on chmod error here because the
            # target path may have RESTRICTED aclmode. Correct permissions
            # get set in below `filesystem.setperm` call which strips ACL
            # if present to strictly enforce `mode`.
            context.middleware.call_sync(
                "filesystem.mkdir",
                FilesystemMkdirData(
                    path=target,
                    options=FilesystemMkdirOptions(mode=mode, raise_chmod_error=False),
                ),
            )
        except CallError as e:
            if e.errno == errno.EEXIST and not os.path.isdir(target):
                raise CallError("Path for home directory already exists and is not a directory", errno.EEXIST)
        except OSError as oe:
            raise CallError(f"Failed to create the home directory ({target}) for user: {oe}")
        else:
            homedir_created = True
    else:
        target = path

    try:
        setperm_job = context.middleware.call_sync(
            "filesystem.setperm",
            {
                "path": target,
                "mode": mode,
                "uid": uid,
                "gid": gid,
                "options": {"stripacl": True},
            },
        )
        setperm_job.wait_sync(raise_error=True)
    except Exception:
        if homedir_created:
            shutil.rmtree(target)
        raise

    return target


def recreate_homedir_if_not_exists(
    context: ServiceContext,
    user: dict[str, Any],
    group: dict[str, Any],
    mode: str,
) -> None:
    # sigh, nothing is stopping someone from removing the homedir
    # from the CLI so recreate the original directory in this case
    if not os.path.isdir(user["home"]):
        if os.path.exists(user["home"]):
            raise CallError(f"{user['home']!r} already exists and is not a directory")

        context.logger.debug("Homedir %r for %r does not exist so recreating it", user["home"], user["username"])
        try:
            os.makedirs(user["home"])
        except Exception:
            raise CallError(f'Failed recreating "{user["home"]}"')
        else:
            context.middleware.call_sync(
                "filesystem.setperm",
                {
                    "path": user["home"],
                    "uid": user["uid"],
                    "gid": group["bsdgrp_gid"],
                    "mode": mode,
                    "options": {"stripacl": True},
                },
            ).wait_sync(raise_error=True)


def update_sshpubkey(context: ServiceContext, homedir: str, user: dict[str, Any], group: str) -> None:
    if "sshpubkey" not in user:
        return
    if not os.path.isdir(homedir):
        return

    sshpath = f"{homedir}/.ssh"
    keysfile = f"{sshpath}/authorized_keys"
    gid = -1

    pubkey = user.get("sshpubkey") or ""
    pubkey = pubkey.strip()
    if pubkey == "":
        try:
            os.unlink(keysfile)
        except OSError:
            pass
        return

    oldpubkey = ""
    try:
        with open(keysfile, "r") as f:
            oldpubkey = f.read().strip()
    except Exception:
        pass

    if pubkey == oldpubkey:
        return

    if not os.path.isdir(sshpath):
        # Since this is security sensitive, we allow raising exception here
        # if mode fails to be set to 0o700
        context.middleware.call_sync(
            "filesystem.mkdir",
            FilesystemMkdirData(path=sshpath, options=FilesystemMkdirOptions(mode="700")),
        )
    if not os.path.isdir(sshpath):
        raise CallError(f"{sshpath} is not a directory")

    # Make extra sure to enforce correct mode on .ssh directory.
    # stripping the ACL will allow subsequent chmod calls to succeed even if
    # dataset aclmode is restricted.
    try:
        gid = context.call_sync2(context.s.group.get_group_obj, GroupGetGroupObj(groupname=group)).gr_gid
    except Exception:
        # leaving gid at -1 avoids altering the GID value.
        context.logger.debug("Failed to convert %s to gid", group, exc_info=True)

    context.middleware.call_sync(
        "filesystem.setperm",
        {
            "path": sshpath,
            "mode": str(700),
            "uid": user["uid"],
            "gid": gid,
            "options": {"recursive": True, "stripacl": True},
        },
    ).wait_sync(raise_error=True)

    with atomic_write(keysfile, "w", uid=user["uid"], gid=gid, perms=0o600) as f:
        f.write(f"{pubkey}\n")


def do_home_copy(
    context: ServiceContext,
    job: Job,
    home_old: str,
    home_new: str,
    username: str,
    new_mode: str | None,
    uid: int,
) -> dict[str, Any] | None:
    if home_old in DEFAULT_HOME_PATH:
        return None

    # We need to set permission and strip ACL first before copying files
    if new_mode is not None:
        mode = new_mode
    else:
        current_mode = stat.S_IMODE(context.middleware.call_sync("filesystem.stat", home_old).mode)
        mode = f"{current_mode:03o}"

    perm_job = context.middleware.call_sync(
        "filesystem.setperm",
        {
            "uid": uid,
            "path": home_new,
            "mode": mode,
            "options": {"stripacl": True},
        },
    )
    perm_job.wait_sync()

    def progress_cb(_dir_stack: Any, state: Any, j: Job) -> None:
        j.set_progress(100, f"Copied {state.cnt} items from {state.current_directory}.")

    stats: CopyTreeStats = copytree(
        home_old,
        home_new,
        CopyTreeConfig(
            exist_ok=True,
            reporting_callback=progress_cb,
            reporting_private_data=job,
        ),
    )
    job.set_progress(
        100,
        (
            f"Successfully copied {stats.dirs} directories, {stats.files} files, "
            f"{stats.symlinks} symlinks for a total of {stats.bytes} bytes of data."
        ),
    )
    return asdict(stats)
