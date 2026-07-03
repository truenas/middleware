from __future__ import annotations

from collections.abc import Iterator
import contextlib
import enum
import os
import shlex
import tempfile
from typing import TYPE_CHECKING

from middlewared.alert.source.rsync import RsyncFailedAlert, RsyncSuccessAlert
from middlewared.service import CallError, ServiceContext
from middlewared.utils.user_context import run_command_with_user_context

from .utils import get_host_key_file_contents_from_ssh_credentials

if TYPE_CHECKING:
    from middlewared.job import Job


class RsyncReturnCode(enum.Enum):
    # from rsync's "errcode.h"
    OK = 0
    SYNTAX = 1  # syntax or usage error
    PROTOCOL = 2  # protocol incompatibility
    FILESELECT = 3  # errors selecting input/output files, dirs
    UNSUPPORTED = 4  # requested action not supported
    STARTCLIENT = 5  # error starting client-server protocol
    SOCKETIO = 10  # error in socket IO
    FILEIO = 11  # error in file IO
    STREAMIO = 12  # error in rsync protocol data stream
    MESSAGEIO = 13  # errors with program diagnostics
    IPC = 14  # error in IPC code
    CRASHED = 15  # sibling crashed
    TERMINATED = 16  # sibling terminated abnormally
    SIGNAL1 = 19  # status returned when sent SIGUSR1
    SIGNAL = 20  # status returned when sent SIGINT, SIGTERM, SIGHUP
    WAITCHILD = 21  # some error returned by waitpid()
    MALLOC = 22  # error allocating core memory buffers
    PARTIAL = 23  # partial transfer
    VANISHED = 24  # file(s) vanished on sender side
    DEL_LIMIT = 25  # skipped some deletes due to --max-delete
    TIMEOUT = 30  # timeout in data send/receive
    CONTIMEOUT = 35  # timeout waiting for daemon connection

    @classmethod
    def nonfatals(cls) -> tuple[int, ...]:
        return tuple([rc.value for rc in [cls.OK, cls.VANISHED, cls.DEL_LIMIT]])


@contextlib.contextmanager
def build_commandline(context: ServiceContext, id_: int) -> Iterator[str]:
    """Helper to generate the rsync command, avoiding code duplication."""
    rsync = context.call_sync2(context.s.rsynctask.get_instance, id_)
    path = shlex.quote(rsync.path)

    with contextlib.ExitStack() as exit_stack:
        line = ["rsync"]
        for name, flag in (
            ("archive", "-a"),
            ("compress", "-zz"),
            ("delayupdates", "--delay-updates"),
            ("delete", "--delete-delay"),
            ("preserveattr", "-X"),
            ("preserveperm", "-p"),
            ("recursive", "-r"),
            ("times", "-t"),
        ):
            if getattr(rsync, name):
                line.append(flag)
        if rsync.extra:
            line.append(" ".join(rsync.extra))

        remote = ""
        if not rsync.ssh_credentials:
            # Do not use username if one is specified in host field
            # See #5096 for more details
            if rsync.remotehost and "@" in rsync.remotehost:
                remote = rsync.remotehost
            else:
                remote = f'"{rsync.user}"@{rsync.remotehost}'

        if rsync.mode == "MODULE":
            module_args = [path, f'rsync://{remote}/"{rsync.remotemodule}"']
            if rsync.direction != "PUSH":
                module_args.reverse()
            line += module_args
        else:
            if rsync.ssh_credentials:
                credentials = context.call_sync2(
                    context.s.keychaincredential.get_of_type,
                    rsync.ssh_credentials.id,
                    "SSH_CREDENTIALS",
                ).attributes.get_secret_value()
                key_pair = context.call_sync2(
                    context.s.keychaincredential.get_of_type,
                    credentials.private_key,
                    "SSH_KEY_PAIR",
                )

                remote = f'"{credentials.username}"@{credentials.host}'
                port: int | None = credentials.port

                private_key = key_pair.attributes.get_secret_value().private_key
                if private_key is None:
                    raise CallError(f"SSH key pair {credentials.private_key} has no private key")

                user = context.middleware.call_sync("user.get_user_obj", {"username": rsync.user})

                private_key_file = exit_stack.enter_context(tempfile.NamedTemporaryFile("w"))
                os.fchmod(private_key_file.fileno(), 0o600)
                os.fchown(private_key_file.fileno(), user["pw_uid"], user["pw_gid"])
                private_key_file.write(private_key)
                private_key_file.flush()

                host_key_file = exit_stack.enter_context(tempfile.NamedTemporaryFile("w"))
                os.fchmod(host_key_file.fileno(), 0o600)
                os.fchown(host_key_file.fileno(), user["pw_uid"], user["pw_gid"])
                host_key_file.write(get_host_key_file_contents_from_ssh_credentials(credentials))
                host_key_file.flush()

                extra_args = f"-i {private_key_file.name} -o UserKnownHostsFile={host_key_file.name}"
            else:
                port = rsync.remoteport
                extra_args = ""

            remote_username, remote_host = remote.rsplit("@", 1)
            if ":" in remote_host:
                remote_host = f"[{remote_host}]"
            remote = f"{remote_username}@{remote_host}"

            line += ["-e", f'"ssh -p {port} -o BatchMode=yes -o StrictHostKeyChecking=yes {extra_args}"']
            path_args = [path, f"{remote}:{shlex.quote(rsync.remotepath)}"]
            if rsync.direction != "PUSH":
                path_args.reverse()
            line += path_args

        if rsync.quiet:
            line += [">", "/dev/null", "2>&1"]

        yield " ".join(line)


def execute_rsync_task(context: ServiceContext, job: Job, id_: int) -> None:
    assert job.logs_fd is not None
    logs_fd = job.logs_fd
    context.middleware.call_sync("network.general.will_perform_activity", "rsync")

    rsync = context.call_sync2(context.s.rsynctask.get_instance, id_)
    if rsync.locked:
        context.call_sync2(context.s.rsynctask.generate_locked_alert, id_)
        return

    with build_commandline(context, id_) as commandline:
        cp = run_command_with_user_context(
            commandline,
            rsync.user,
            output=False,
            callback=lambda v: logs_fd.write(v),
        )

    for klass in ("RsyncSuccess", "RsyncFailed") if not rsync.quiet else ():
        context.call_sync2(context.s.alert.oneshot_delete, klass, rsync.id)

    if cp.returncode not in RsyncReturnCode.nonfatals():
        err = None
        if cp.returncode == RsyncReturnCode.STREAMIO.value and rsync.compress:
            err = (
                "rsync command with compression enabled failed with STREAMIO error. "
                "This may indicate that remote server lacks support for the new-style "
                "compression used by TrueNAS."
            )

        if not rsync.quiet:
            context.call_sync2(
                context.s.alert.oneshot_create,
                RsyncFailedAlert(
                    id=rsync.id,
                    direction=rsync.direction,
                    path=rsync.path,
                ),
            )

        if err:
            msg = f"{err} Check logs for further information"
        else:
            try:
                rc_name = RsyncReturnCode(cp.returncode).name
            except ValueError:
                rc_name = "UNKNOWN"

            msg = f"rsync command returned {cp.returncode} - {rc_name}. Check logs for further information."
        raise CallError(msg)

    elif not rsync.quiet:
        context.call_sync2(
            context.s.alert.oneshot_create,
            RsyncSuccessAlert(
                id=rsync.id,
                direction=rsync.direction,
                path=rsync.path,
            ),
        )
