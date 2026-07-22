import asyncio
import collections
import contextlib
import errno
import fcntl
import os
import queue
import select
import signal
import struct
import termios
import threading
import time

from truenas_api_client import json

from middlewared.api.base.server.app import App
from middlewared.api.base.server.ws_handler.base import BaseWebSocketHandler
from middlewared.plugins.account_.constants import DEFAULT_HOME_PATH
from middlewared.service_exception import (
    CallError,
    ErrnoMixin,
)
from middlewared.utils.auth import ShellAppType, ShellTokenAuthError
from middlewared.utils.os import close_fds, terminate_pid
from middlewared.utils.threading import run_coro_threadsafe

__all__ = ("ShellApplication",)

ShellResize = collections.namedtuple("ShellResize", ["cols", "rows"])

# /bin/sh in most app/container images is dash or busybox sh, which lack
# readline — up-arrow / history / line. Default to bash when the image
# ships it, otherwise fall back to whatever /bin/sh is. Used as the script
# argument to `sh -c` by both the app and container shell paths.
BASH_FALLBACK_SCRIPT = "if command -v bash >/dev/null 2>&1; then exec bash -l; else exec sh; fi"


def _audit_target(shell_type, options):
    if shell_type is ShellAppType.VM:
        return {"vm_id": options["vm_id"]}
    if shell_type is ShellAppType.APP:
        return {"app_name": options["app_name"], "container_id": options["container_id"]}
    if shell_type is ShellAppType.CONTAINER:
        return {"container_id": options["container_id"]}
    return None


class ShellWorkerThread(threading.Thread):
    """
    Worker thread responsible for forking and running the shell
    and spawning the reader and writer threads.
    """

    def __init__(self, middleware, ws, input_queue, loop, username, options, homedir):
        self.middleware = middleware
        self.ws = ws
        self.input_queue = input_queue
        self.loop = loop
        self.shell_pid = None
        self.master_fd = None
        self.command = self.get_command(username, options)
        self.homedir = homedir
        self.username = username
        self._die = False
        super(ShellWorkerThread, self).__init__(daemon=True)

    def get_command(self, username, options):
        if options.get("vm_id"):
            return [
                "/usr/bin/virsh",
                "-c",
                "qemu+unix:///system?socket=/run/truenas_libvirt/libvirt-sock",
                "console",
                f'{options["vm_data"]["uuid"]}',
            ]
        elif options.get("app_name"):
            return [
                "/usr/bin/docker",
                "exec",
                "-it",
                options["container_id"],
                "/bin/sh", "-c", self._shell_script(options),
            ]
        elif options.get("container_id"):
            # nsenter argv already terminates with `/bin/sh -c`; append the
            # script as the single trailing argument so it is what `sh -c`
            # actually executes (rather than being interpreted as $0/$1).
            return options["nsenter"] + [self._shell_script(options)]
        else:
            return ["/usr/bin/login", "-p", "-f", username]

    def _shell_script(self, options):
        # Callers (currently only integration tests) may override the script
        # passed to the container's `/bin/sh -c`. Default falls back to bash
        # when available, otherwise sh.
        return options.get("command") or BASH_FALLBACK_SCRIPT

    def resize(self, cols, rows):
        self.input_queue.put(ShellResize(cols, rows))

    def _shell_alive(self):
        pid = self.shell_pid
        if pid is None:
            return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        return True

    def run(self):
        self.shell_pid, self.master_fd = os.forkpty()
        if self.shell_pid == 0:
            close_fds(3)
            homedir = self.homedir or DEFAULT_HOME_PATH
            try:
                os.chdir(homedir)
            except FileNotFoundError:
                os.chdir(DEFAULT_HOME_PATH)
            except Exception:
                self.middleware.logger.error(
                    "%s: Failed to chdir into home directory for user [%s] in ShellWorkerThread.run",
                    homedir, self.username,  exc_info=True
                )
                os.chdir(DEFAULT_HOME_PATH)

            env = {
                "TERM": "xterm",
                "HOME": homedir,
                "PATH": "/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:/usr/local/bin:/root/bin",
                "LC_ALL": "C.UTF-8",
            }
            os.execve(self.command[0], self.command, env)
            # execve never returns on success; if we reach here, it failed
            error_msg = f"Failed to execute {self.command[0]}\r\n".encode()
            os.write(2, error_msg)
            os._exit(1)

        # Terminal baudrate affects input queue size
        attr = termios.tcgetattr(self.master_fd)
        attr[4] = attr[5] = termios.B921600
        termios.tcsetattr(self.master_fd, termios.TCSANOW, attr)

        def reader():
            """
            Reader thread for reading from pty file descriptor
            and forwarding it to the websocket.
            """
            # run() closes master_fd only after this thread exits
            master_fd = self.master_fd
            shell_pid = self.shell_pid
            poller = select.poll()
            poller.register(master_fd, select.POLLIN)
            eio_deadline = None
            try:
                while not self._die:
                    # Use poll to wait for data (1 second timeout)
                    events = poller.poll(1000)  # timeout in milliseconds
                    if not events:
                        # Timeout, check if child is still alive
                        if self._shell_alive():
                            continue
                        break

                    try:
                        read = os.read(master_fd, 1024)
                    except OSError:
                        read = b""
                    if read == b"":
                        # EIO/EOF means no process has the slave open -- transient during login(1)
                        # vhangup+reopen. Fatal if the child is gone or the slave stays abandoned.
                        if not self._shell_alive():
                            break
                        if eio_deadline is None:
                            eio_deadline = time.monotonic() + 5
                        elif time.monotonic() >= eio_deadline:
                            self.middleware.logger.warning(
                                "%d: pty slave abandoned; terminating shell session", shell_pid
                            )
                            self.abort()
                            break
                        time.sleep(0.05)
                        continue

                    eio_deadline = None
                    fut = asyncio.run_coroutine_threadsafe(self.ws.send_bytes(read), loop=self.loop)
                    try:
                        fut.result(timeout=30)
                    except TimeoutError:
                        # A stalled client that stops draining but keeps acking zero-window probes
                        # never fails at the TCP level, so the send must be bounded here.
                        fut.cancel()
                        raise
            except BaseException:
                # BaseException: CancelledError from the ws send must not kill this thread
                # silently; during teardown the ws may already be closed, which is not an error.
                if not self._die:
                    self.middleware.logger.error("Error in ShellWorkerThread.reader", exc_info=True)
                    self.abort()
            finally:
                poller.unregister(master_fd)

        def writer():
            """
            Writer thread for reading from input_queue and write to
            the shell pty file descriptor.
            """
            # run() closes master_fd only after this thread exits
            master_fd = self.master_fd
            try:
                while not self._die:
                    try:
                        get = self.input_queue.get(timeout=1)
                        if get is None:
                            # shutdown sentinel from abort()/run()
                            break

                        if isinstance(get, ShellResize):
                            fcntl.ioctl(
                                master_fd,
                                termios.TIOCSWINSZ,
                                struct.pack("HHHH", get.rows, get.cols, 0, 0),
                            )
                        else:
                            os.write(master_fd, get)
                    except queue.Empty:
                        # If we timeout waiting in input query lets make sure
                        # the shell process is still alive
                        if not self._shell_alive():
                            break
                    except OSError:
                        # EIO means no process has the slave open -- transient during login(1)
                        # vhangup+reopen. Fatal only if the child is gone.
                        if not self._shell_alive():
                            break
                        time.sleep(0.05)
            except BaseException:
                self.middleware.logger.error(
                    "Error in ShellWorkerThread.writer", exc_info=True
                )
                self.abort()

        t_reader = t_writer = None
        try:
            if self._die:
                # abort() ran before the fork and had no pid to kill. Kill the pid directly: the
                # child may not have called setsid() yet, so its process group may still be ours.
                # The reap below collects the zombie immediately.
                with contextlib.suppress(ProcessLookupError):
                    os.kill(self.shell_pid, signal.SIGKILL)

            t_reader = threading.Thread(target=reader, daemon=True)
            t_reader.start()

            t_writer = threading.Thread(target=writer, daemon=True)
            t_writer.start()

            # Reap the child so terminate_pid() and the threads' liveness checks see it exit;
            # abort() unblocks this by killing the child. WNOHANG polling so an unkillable
            # (D-state) child cannot strand this thread and the fds it owns forever.
            give_up_at = None
            while True:
                try:
                    if os.waitpid(self.shell_pid, os.WNOHANG)[0]:
                        self.shell_pid = None
                        break
                except ChildProcessError:
                    self.shell_pid = None
                    break

                if self._die:
                    if give_up_at is None:
                        give_up_at = time.monotonic() + 5
                    elif time.monotonic() >= give_up_at:
                        self.middleware.logger.error(
                            "%d: shell child did not exit after kill; abandoning reap", self.shell_pid
                        )
                        break

                time.sleep(0.2 if self._die else 1)
        except BaseException:
            self.middleware.logger.error("Error in ShellWorkerThread.run", exc_info=True)
            self.abort()
        finally:
            # Close master_fd only after both threads have exited; closing
            # earlier lets the fd number be recycled under them.
            self.input_queue.put(None)
            if t_reader is not None:
                t_reader.join()
            if t_writer is not None:
                t_writer.join()
            self.close_master_fd()
            run_coro_threadsafe(self.ws.close(), self.loop)

    def die(self):
        self._die = True

    def abort(self):
        # Signal the threads; run() joins them and closes master_fd
        self.die()
        self.input_queue.put(None)

        # Close websocket
        run_coro_threadsafe(self.ws.close(), self.loop)

        # Child death wakes the reader (EOF/HUP) and the waitpid() in run()
        if self.shell_pid:
            with contextlib.suppress(ProcessLookupError):
                terminate_pid(self.shell_pid, timeout=2, use_pgid=True)

    def close_master_fd(self):
        # Atomic swap so that concurrent calls don't race to close the same fd (GIL makes the swap atomic).
        fd, self.master_fd = self.master_fd, None
        if fd is not None:
            with contextlib.suppress(OSError):
                os.close(fd)


class ShellConnectionData:
    id = None
    t_worker = None


class ShellApplication:
    shells = {}

    def __init__(self, middleware):
        self.middleware = middleware

    async def ws_handler(self, request):
        ws, prepared = await self.middleware.create_and_prepare_ws(request)
        if not prepared:
            return ws

        handler = BaseWebSocketHandler(self.middleware)
        origin = await handler.get_origin(request)
        if not await self.middleware.ws_can_access(ws, origin):
            return ws

        app = App(origin)
        app.websocket = True

        conndata = ShellConnectionData()
        conndata.id = app.session_id

        try:
            await self.run(ws, app, conndata)
        except Exception:
            if conndata.t_worker:
                await self.worker_kill(conndata.t_worker)
            self.middleware.logger.error('Failed to start shell console', exc_info=True)
        finally:
            self.shells.pop(conndata.id, None)
            return ws

    async def run(self, ws, app, conndata):
        origin = app.origin
        # Each connection will have its own input queue
        input_queue = queue.Queue()
        authenticated = False
        session_audit_info = None

        try:
            async for msg in ws:
                if authenticated:
                    # Add content of every message received in input queue
                    input_queue.put(msg.data)
                else:
                    try:
                        data = json.loads(msg.data)
                    except json.decoder.JSONDecodeError:
                        continue

                    token_id = data.get("token")
                    if not token_id:
                        continue

                    options = data.get("options", {})

                    # vm_id selects a VM shell and is mutually exclusive with
                    # the app/container options. APP shells legitimately
                    # specify both app_name and container_id, so those two are
                    # not in conflict with each other.
                    if options.get("vm_id") and (
                        options.get("app_name") or options.get("container_id")
                    ):
                        raise CallError(
                            "vm_id cannot be combined with app_name or container_id"
                        )

                    if options.get("vm_id"):
                        shell_type = ShellAppType.VM
                    elif options.get("app_name"):
                        shell_type = ShellAppType.APP
                    elif options.get("container_id"):
                        shell_type = ShellAppType.CONTAINER
                    else:
                        shell_type = ShellAppType.HOST

                    audit_target = _audit_target(shell_type, options)

                    token = await self.middleware.call(
                        "auth.get_token_for_shell_application", token_id, origin, shell_type
                    )
                    if not token:
                        await self.middleware.log_audit_message(app, "WEBSHELL_AUTHENTICATION", {
                            "shell_type": shell_type.value,
                            "target": audit_target,
                            "username": None,
                            "error": "invalid token",
                        }, False)
                        await ws.send_json(
                            {
                                "msg": "failed",
                                "error": {
                                    "error": ErrnoMixin.ENOTAUTHENTICATED,
                                    "reason": "Invalid token",
                                },
                            }
                        )
                        continue
                    if token.get("error") == ShellTokenAuthError.WEB_SHELL_DENIED:
                        app.authenticated_credentials = token["credentials"]
                        await self.middleware.log_audit_message(app, "WEBSHELL_AUTHENTICATION", {
                            "shell_type": shell_type.value,
                            "target": audit_target,
                            "username": token["username"],
                            "error": "web_shell privilege not granted",
                        }, False)
                        await ws.send_json(
                            {
                                "msg": "failed",
                                "error": {
                                    "error": errno.EACCES,
                                    "reason": "Web shell privilege not granted for this account",
                                },
                            }
                        )
                        continue
                    if token.get("error") == ShellTokenAuthError.MISSING_ROLE:
                        app.authenticated_credentials = token["credentials"]
                        await self.middleware.log_audit_message(app, "WEBSHELL_AUTHENTICATION", {
                            "shell_type": shell_type.value,
                            "target": audit_target,
                            "username": token["username"],
                            "error": f"missing required role: {token['required_role']}",
                        }, False)
                        await ws.send_json(
                            {
                                "msg": "failed",
                                "error": {
                                    "error": errno.EACCES,
                                    "reason": (
                                        f"Missing required role for {shell_type.value} shell: "
                                        f"{token['required_role']}"
                                    ),
                                },
                            }
                        )
                        continue

                    app.authenticated_credentials = token["credentials"]

                    if shell_type is ShellAppType.CONTAINER:
                        # Enrich audit target with the friendly container name
                        # so admins reviewing logs don't have to cross-reference
                        # numeric ids. Done only on the auth-success path because
                        # the lookup would otherwise leak existence to failed
                        # attempts.
                        container = await self.middleware.call(
                            "container.get_instance", options["container_id"]
                        )
                        audit_target = {
                            **audit_target,
                            "container_name": container["name"],
                        }

                    session_audit_info = {
                        "shell_type": shell_type.value,
                        "target": audit_target,
                        "username": token["username"],
                    }
                    await self.middleware.log_audit_message(app, "WEBSHELL_AUTHENTICATION", {
                        **session_audit_info,
                        "error": None,
                    }, True)

                    authenticated = True

                    if shell_type is ShellAppType.VM:
                        options["vm_data"] = await self.middleware.call(
                            "vm.get_instance", options["vm_id"]
                        )
                    elif shell_type is ShellAppType.APP:
                        if not options.get("container_id"):
                            raise CallError("Container id must be specified")
                        choices = await self.middleware.call(
                            "app.container_console_choices", options["app_name"]
                        )
                        if options["container_id"] not in choices:
                            raise CallError("Provided container id is not valid")
                    elif shell_type is ShellAppType.CONTAINER:
                        # container.nsenter takes the full container dict
                        # (it reads container["status"]["pid"], ["uuid"],
                        # ...), not the id — reuse the lookup from above.
                        options["nsenter"] = await self.middleware.call(
                            "container.nsenter", container,
                        )

                    try:
                        user_obj = await self.middleware.call("user.get_user_obj", {"username": token["username"]})
                    except KeyError:
                        raise CallError(f'{token["username"]}: user does not exist')

                    conndata.t_worker = ShellWorkerThread(
                        middleware=self.middleware,
                        ws=ws,
                        input_queue=input_queue,
                        loop=asyncio.get_event_loop(),
                        username=token["username"],
                        homedir=user_obj["pw_dir"],
                        options=options,
                    )
                    conndata.t_worker.start()

                    self.shells[conndata.id] = conndata.t_worker

                    await ws.send_json(
                        {
                            "msg": "connected",
                            "id": conndata.id,
                        }
                    )

            # If connection was not authenticated, return earlier
            if not authenticated:
                return ws

            if conndata.t_worker:
                self.middleware.create_task(self.worker_kill(conndata.t_worker))

            return ws
        finally:
            if session_audit_info is not None:
                await self.middleware.log_audit_message(
                    app, "WEBSHELL_LOGOUT", session_audit_info, True,
                )

    async def worker_kill(self, t_worker):
        await self.middleware.run_in_thread(t_worker.abort)
