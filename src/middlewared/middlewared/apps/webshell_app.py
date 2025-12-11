import asyncio
import collections
import contextlib
import fcntl
import os
import queue
import select
import struct
import termios
import threading
import time

from middlewared.api.base.server.ws_handler.base import BaseWebSocketHandler
from middlewared.service_exception import (
    CallError,
    ErrnoMixin,
    MatchNotFound,
)
from middlewared.utils.crypto import ssl_uuid4
from middlewared.utils.os import close_fds, terminate_pid
from truenas_api_client import json

__all__ = ("ShellApplication",)

ShellResize = collections.namedtuple("ShellResize", ["cols", "rows"])


class ShellWorkerThread(threading.Thread):
    """
    Worker thread responsible for forking and running the shell
    and spawning the reader and writer threads.
    """

    def __init__(self, middleware, ws, input_queue, loop, username, as_root, options):
        self.middleware = middleware
        self.ws = ws
        self.input_queue = input_queue
        self.loop = loop
        self.shell_pid = None
        self.master_fd = None
        self.command, self.sudo_warning = self.get_command(username, as_root, options)
        self._die = False
        super(ShellWorkerThread, self).__init__(daemon=True)

    def get_command(self, username, as_root, options):
        allowed_options = ("vm_id", "app_name", "container_id")
        if all(options.get(k) for k in allowed_options):
            raise CallError(
                f'Only one option is supported from {", ".join(allowed_options)}'
            )

        if options.get("vm_id"):
            command = [
                "/usr/bin/virsh",
                "-c",
                "qemu+unix:///system?socket=/run/truenas_libvirt/libvirt-sock",
                "console",
                f'{options["vm_data"]["uuid"]}',
            ]
            if not as_root:
                command = ["/usr/bin/sudo", "-H", "-u", username] + command
            return command, not as_root
        elif options.get("app_name"):
            command = [
                "/usr/bin/docker",
                "exec",
                "-it",
                options["container_id"],
                options.get("command", "/bin/bash"),
            ]
            if not as_root:
                command = ["/usr/bin/sudo", "-H", "-u", username] + command
            return command, not as_root
        elif options.get("container_id"):
            command = options["nsenter"] + [options["command"]]
            if not as_root:
                command = ["/usr/bin/sudo", "-H", "-u", username] + command
            return command, not as_root
        else:
            return ["/usr/bin/login", "-p", "-f", username], False

    def resize(self, cols, rows):
        self.input_queue.put(ShellResize(cols, rows))

    def run(self):
        self.shell_pid, self.master_fd = os.forkpty()
        if self.shell_pid == 0:
            close_fds(3)
            os.chdir("/root")
            env = {
                "TERM": "xterm",
                "HOME": "/root",
                "LANG": "en_US.UTF-8",
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

        if self.sudo_warning:
            asyncio.run_coroutine_threadsafe(
                self.ws.send_bytes(
                    (
                        f"WARNING: Your user does not have sudo privileges so {self.command[4]} command will run\r\n"
                        f"on your behalf. This might cause permission issues.\r\n\r\n"
                    ).encode("utf-8")
                ),
                loop=self.loop,
            ).result()

        def reader():
            """
            Reader thread for reading from pty file descriptor
            and forwarding it to the websocket.
            """
            # Use a local copy of master_fd to avoid race condition with abort()
            master_fd = self.master_fd
            poller = select.poll()
            poller.register(master_fd, select.POLLIN)
            try:
                while True:
                    # Use poll to wait for data (1 second timeout)
                    try:
                        events = poller.poll(1000)  # timeout in milliseconds
                        if not events:
                            # Timeout, check if child is still alive
                            try:
                                os.kill(self.shell_pid, 0)
                                continue
                            except ProcessLookupError:
                                break
                    except OSError:
                        # Expected when master_fd is closed by abort()
                        break

                    try:
                        read = os.read(master_fd, 1024)
                    except OSError:
                        # Expected when PTY closes or abort() closes master_fd
                        break
                    if read == b"":
                        break
                    asyncio.run_coroutine_threadsafe(
                        self.ws.send_bytes(read), loop=self.loop
                    ).result()
            except Exception:
                self.middleware.logger.error(
                    "Error in ShellWorkerThread.reader", exc_info=True
                )
                self.abort()
            finally:
                with contextlib.suppress(OSError):
                    poller.unregister(master_fd)

        def writer():
            """
            Writer thread for reading from input_queue and write to
            the shell pty file descriptor.
            """
            # Use a local copy of master_fd to avoid race condition with abort()
            master_fd = self.master_fd
            try:
                while True:
                    try:
                        get = self.input_queue.get(timeout=1)
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
                        try:
                            os.kill(self.shell_pid, 0)
                        except ProcessLookupError:
                            break
                    except OSError:
                        # Expected when master_fd is closed by abort()
                        break
            except Exception:
                self.middleware.logger.error(
                    "Error in ShellWorkerThread.writer", exc_info=True
                )
                self.abort()

        t_reader = threading.Thread(target=reader, daemon=True)
        t_reader.start()

        t_writer = threading.Thread(target=writer, daemon=True)
        t_writer.start()

        # Wait for shell to exit
        while True:
            try:
                pid, rv = os.waitpid(self.shell_pid, os.WNOHANG)
            except ChildProcessError:
                break
            if self._die:
                return
            if pid <= 0:
                time.sleep(1)

        t_reader.join()
        t_writer.join()
        self.close_master_fd()
        asyncio.run_coroutine_threadsafe(self.ws.close(), self.loop)

    def die(self):
        self._die = True

    def abort(self):
        # Close websocket
        asyncio.run_coroutine_threadsafe(self.ws.close(), self.loop)

        # Close the master FD
        if self.master_fd is not None:
            self.close_master_fd()

        # Terminate the child process
        if self.shell_pid:
            with contextlib.suppress(ProcessLookupError):
                terminate_pid(self.shell_pid, timeout=2, use_pgid=True)

        # Set die flag
        self.die()

    def close_master_fd(self):
        """Raises TypeError if self.master_fd is None."""
        with contextlib.suppress(OSError):
            os.close(self.master_fd)
            self.master_fd = None


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

        conndata = ShellConnectionData()
        conndata.id = str(ssl_uuid4())

        try:
            await self.run(ws, origin, conndata)
        except Exception:
            if conndata.t_worker:
                await self.worker_kill(conndata.t_worker)
            self.middleware.logger.error('Failed to start shell console', exc_info=True)
        finally:
            self.shells.pop(conndata.id, None)
            return ws

    async def run(self, ws, origin, conndata):
        # Each connection will have its own input queue
        input_queue = queue.Queue()
        authenticated = False

        async for msg in ws:
            if authenticated:
                # Add content of every message received in input queue
                input_queue.put(msg.data)
            else:
                try:
                    data = json.loads(msg.data)
                except json.decoder.JSONDecodeError:
                    continue

                token = data.get("token")
                if not token:
                    continue

                token = await self.middleware.call(
                    "auth.get_token_for_shell_application", token, origin
                )
                if not token:
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

                authenticated = True

                options = data.get("options", {})
                if options.get("vm_id"):
                    options["vm_data"] = await self.middleware.call(
                        "vm.get_instance", options["vm_id"]
                    )

                if options.get("container_id"):
                    options["nsenter"] = await self.middleware.call(
                        "container.nsenter",
                        await self.middleware.call("container.get_instance", options["container_id"]),
                    )
                    options["command"] = options.get("command") or "/bin/sh"

                if options.get("app_name"):
                    if not options.get("container_id"):
                        raise CallError("Container id must be specified")
                    if options["container_id"] not in await self.middleware.call(
                        "app.container_console_choices", options["app_name"]
                    ):
                        raise CallError("Provided container id is not valid")

                # By default we want to run virsh with user's privileges and assume all "permission denied"
                # errors this can cause, unless the user has a sudo permission for all commands; in that case, let's
                # run them straight with root privileges.
                as_root = False
                try:
                    user = await self.middleware.call(
                        "user.query",
                        [["username", "=", token["username"]], ["local", "=", True]],
                        {"get": True},
                    )
                except MatchNotFound:
                    # Currently only local users can be sudoers
                    pass
                else:
                    if (
                        "ALL" in user["sudo_commands"]
                        or "ALL" in user["sudo_commands_nopasswd"]
                    ):
                        as_root = True
                    else:
                        for group in await self.middleware.call(
                            "group.query",
                            [["id", "in", user["groups"]], ["local", "=", True]],
                        ):
                            if (
                                "ALL" in group["sudo_commands"]
                                or "ALL" in group["sudo_commands_nopasswd"]
                            ):
                                as_root = True
                                break

                conndata.t_worker = ShellWorkerThread(
                    middleware=self.middleware,
                    ws=ws,
                    input_queue=input_queue,
                    loop=asyncio.get_event_loop(),
                    username=token["username"],
                    as_root=as_root,
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

    async def worker_kill(self, t_worker):
        await self.middleware.run_in_thread(t_worker.abort)
