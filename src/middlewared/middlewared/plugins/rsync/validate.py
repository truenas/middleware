from __future__ import annotations

import asyncio
import glob
import os
import pathlib
import shlex
from typing import TYPE_CHECKING, Any

import asyncssh

from middlewared.service import CallError, ValidationErrors
from middlewared.utils import run

from .utils import get_host_key_file_contents_from_ssh_credentials

if TYPE_CHECKING:
    from .crud import RsyncTaskServicePart


async def get_ssh_credentials_connect_kwargs(
    part: RsyncTaskServicePart, verrors: ValidationErrors, cred_id: int, schema: str
) -> dict[str, Any] | None:
    """Return None if the keychain credential with id `cred_id` cannot be retrieved."""
    try:
        ssh_credentials = await part.call2(
            part.s.keychaincredential.get_of_type,
            cred_id,
            "SSH_CREDENTIALS",
        )
    except CallError as e:
        verrors.add(f"{schema}.ssh_credentials", e.errmsg)
        return None

    cred_attrs = ssh_credentials.attributes.get_secret_value()
    ssh_keypair = await part.call2(
        part.s.keychaincredential.get_of_type,
        cred_attrs.private_key,
        "SSH_KEY_PAIR",
    )
    private_key = ssh_keypair.attributes.get_secret_value().private_key
    if private_key is None:
        verrors.add(f"{schema}.ssh_credentials", "SSH key pair has no private key")
        return None

    return {
        "host": cred_attrs.host,
        "port": cred_attrs.port,
        "username": cred_attrs.username,
        "client_keys": [asyncssh.import_private_key(private_key)],
        "known_hosts": asyncssh.SSHKnownHosts(get_host_key_file_contents_from_ssh_credentials(cred_attrs)),
    }


def get_connect_kwargs(
    verrors: ValidationErrors, data: dict[str, Any], schema: str, pw_dir: str
) -> dict[str, Any] | None:
    """Return None if there are no valid private key files in the home directory `pw_dir`."""
    remote_host, remote_port = data["remotehost"], data["remoteport"]

    if not remote_host:
        verrors.add(f"{schema}.remotehost", "This field is required")

    if not remote_port:
        verrors.add(f"{schema}.remoteport", "This field is required")

    search = os.path.join(pw_dir, ".ssh", "id_[edr]*")
    exclude_from_search = os.path.join(pw_dir, ".ssh", "id_[edr]*pub")
    key_files = set(glob.glob(search)) - set(glob.glob(exclude_from_search))

    if not key_files:
        verrors.add(
            f"{schema}.user",
            "In order to use rsync over SSH you need a user with a private key (DSA/ECDSA/RSA) set up in home dir.",
        )

    if verrors:
        return None

    for file in set(key_files):
        # file holds a private key and it's permissions should be 600
        if os.stat(file).st_mode & 0o077 != 0:
            verrors.add(
                f"{schema}.user",
                f"Permissions {str(oct(os.stat(file).st_mode & 0o777))[2:]} for {file} are too open. "
                f"Please correct them by running chmod 600 {file}",
            )
            key_files.discard(file)

    if "@" in remote_host:
        remote_username, remote_host = remote_host.rsplit("@", 1)
    else:
        remote_username = data["user"]

    return {
        "host": remote_host,
        "port": remote_port,
        "username": remote_username,
        "client_keys": key_files,
    }


async def get_known_hosts(
    part: RsyncTaskServicePart,
    verrors: ValidationErrors,
    schema: str,
    known_hosts_path: pathlib.Path,
    ssh_dir_path: pathlib.Path,
    ssh_keyscan: bool,
    host: str,
    port: str,
    pw_uid: int,
    pw_gid: int,
) -> asyncssh.SSHKnownHosts | None:
    try:
        try:
            known_hosts_text = await part.middleware.run_in_thread(known_hosts_path.read_text)
        except FileNotFoundError:
            known_hosts_text = ""

        known_hosts = asyncssh.SSHKnownHosts(known_hosts_text)
    except Exception as e:
        verrors.add(
            f"{schema}.remotehost",
            f"Failed to load {known_hosts_path}: {e}",
        )
        return None

    if not ssh_keyscan or known_hosts.match(host, "", None)[0]:
        return known_hosts

    if known_hosts_text and not known_hosts_text.endswith("\n"):
        known_hosts_text += "\n"

    known_hosts_text += (
        await run(
            ["ssh-keyscan", "-p", port, host],
            encoding="utf-8",
            errors="ignore",
        )
    ).stdout

    # If for whatever reason the dir does not exist, let's create it
    # An example of this is when we run rsync tests we nuke the directory
    def handle_ssh_dir() -> None:
        try:
            ssh_dir_path.mkdir(0o700)
        except FileExistsError:
            pass

        os.chown(ssh_dir_path.absolute(), pw_uid, pw_gid)
        known_hosts_path.write_text(known_hosts_text)
        os.chown(known_hosts_path.absolute(), pw_uid, pw_gid)

    await part.middleware.run_in_thread(handle_ssh_dir)

    return asyncssh.SSHKnownHosts(known_hosts_text)


async def validate_remote_path(
    verrors: ValidationErrors, schema: str, connect_kwargs: dict[str, Any], remote_path: str
) -> None:
    try:
        async with await asyncssh.connect(
            **connect_kwargs,
            options=asyncssh.SSHClientConnectionOptions(connect_timeout=5),
        ) as conn:
            await conn.run(f"ls -d {shlex.quote(remote_path)}", check=True)
    except asyncio.TimeoutError:
        verrors.add(f"{schema}.remotehost", "SSH timeout occurred. Remote path cannot be validated.")
    except OSError as e:
        if e.errno == 113:
            verrors.add(
                f"{schema}.remotehost",
                f"Connection to the remote host {connect_kwargs['host']} on port {connect_kwargs['port']} failed.",
            )
        else:
            verrors.add(f"{schema}.remotehost", e.__str__())
    except asyncssh.HostKeyNotVerifiable as e:
        verrors.add(
            f"{schema}.remotehost",
            f"Failed to verify remote host key: {e.reason}",
            CallError.ESSLCERTVERIFICATIONERROR,
        )
    except asyncssh.DisconnectError as e:
        verrors.add(
            f"{schema}.remotehost",
            f"Disconnect Error [error code {e.code}: {e.reason}] was generated when trying to "
            f"communicate with remote host {connect_kwargs['host']} and remote user "
            f"{connect_kwargs['username']}.",
        )
    except asyncssh.ProcessError as e:
        stderr = e.stderr
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="ignore")
        verrors.add(
            f"{schema}.remotepath",
            "The Remote Path you specified does not exist or is not a directory. "
            "Either create one yourself on the remote machine or uncheck the "
            f"validate_rpath field. {stderr.strip()}",
        )
    except asyncssh.Error as e:
        if e.__class__.__name__ in e.__str__():
            exception_reason = e.__str__()
        else:
            exception_reason = e.__class__.__name__ + " " + e.__str__()
        verrors.add(
            f"{schema}.remotepath", f"Remote Path could not be validated. An exception was raised. {exception_reason}"
        )


async def validate_ssh_task(
    part: RsyncTaskServicePart, verrors: ValidationErrors, data: dict[str, Any], schema: str, user: dict[str, Any]
) -> None:
    ssh_dir_path = pathlib.Path(os.path.join(user["pw_dir"], ".ssh"))
    known_hosts_path = pathlib.Path(os.path.join(ssh_dir_path, "known_hosts"))

    known_hosts_location: Any
    if data["ssh_credentials"]:
        connect_kwargs = await get_ssh_credentials_connect_kwargs(part, verrors, data["ssh_credentials"], schema)
        known_hosts_location = "SSH Connection Settings"
    else:
        connect_kwargs = get_connect_kwargs(verrors, data, schema, user["pw_dir"])
        known_hosts_location = known_hosts_path

    remote_path: str = data.get("remotepath") or ""
    if not remote_path:
        verrors.add(f"{schema}.remotepath", "This field is required")

    if not (data["enabled"] and connect_kwargs):
        return

    if "known_hosts" not in connect_kwargs:
        if known_hosts := await get_known_hosts(
            part,
            verrors,
            schema,
            known_hosts_path,
            ssh_dir_path,
            data["ssh_keyscan"],
            connect_kwargs["host"],
            str(connect_kwargs["port"]),
            user["pw_uid"],
            user["pw_gid"],
        ):
            connect_kwargs["known_hosts"] = known_hosts
            known_hosts_location = known_hosts_path

    verrors.check()

    if data["validate_rpath"]:
        await validate_remote_path(verrors, schema, connect_kwargs, remote_path)
    elif not connect_kwargs["known_hosts"].match(connect_kwargs["host"], "", None)[0]:
        verrors.add(
            f"{schema}.remotehost",
            f"Host key not found in {known_hosts_location}",
            CallError.ESSLCERTVERIFICATIONERROR,
        )


async def validate_rsync_task(
    part: RsyncTaskServicePart, data: dict[str, Any], schema: str
) -> tuple[ValidationErrors, dict[str, Any]]:
    verrors = ValidationErrors()

    # Windows users can have spaces in their usernames
    # http://www.freebsd.org/cgi/query-pr.cgi?pr=164808

    username = data["user"]
    if " " in username:
        verrors.add(f"{schema}.user", "User names cannot have spaces")
        raise verrors

    try:
        user = await part.middleware.call("user.get_user_obj", {"username": username})
    except KeyError:
        user = None

    if not user:
        verrors.add(f"{schema}.user", f'Provided user "{username}" does not exist')
        raise verrors

    await part.validate_path_field(data, schema, verrors, split_path=True)

    try:
        shlex.split(" ".join(data["extra"]).replace('"', r'"\"').replace("'", r'"\"'))
    except ValueError as e:
        verrors.add(f"{schema}.extra", f"Please specify valid value: {e}")

    match data["mode"]:
        case "MODULE":
            if not data["remotehost"]:
                verrors.add(f"{schema}.remotehost", "This field is required")

            if not data["remotemodule"]:
                verrors.add(f"{schema}.remotemodule", "This field is required")

            if data["ssh_credentials"]:
                verrors.add(f"{schema}.ssh_credentials", "SSH credentials can't be used when mode is MODULE")

        case "SSH":
            await validate_ssh_task(part, verrors, data, schema, user)

    data.pop("validate_rpath", None)
    data.pop("ssh_keyscan", None)

    return verrors, data
