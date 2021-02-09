import asyncio
from queue import Full, Queue
import re
import select
import socketserver

from middlewared.event import EventSource
from middlewared.service import private, Service
from middlewared.utils import start_daemon_thread


class GraphiteServer(socketserver.TCPServer):
    allow_reuse_address = True


class GraphiteHandler(socketserver.BaseRequestHandler):
    middleware = None

    def handle(self):
        last = b""
        while True:
            data = b""
            # Try to read a batch of updates at once, instead of breaking per message size
            while True:
                if not select.select([self.request.fileno()], [], [], 0.1)[0] and data != b"":
                    break
                msg = self.request.recv(1428)
                if msg == b"":
                    break
                data += msg
            if data == b"":
                break
            if last:
                data = last + data
                last = b""
            lines = (last + data).split(b"\r\n")
            if lines[-1] != b"":
                last = lines[-1]

            batch = []
            for line in lines[:-1]:
                line, value, timestamp = line.decode().split()

                name = line.split(".", 1)[1]
                if name.endswith(".value"):
                    name = name[:-len(".value")]

                value = value
                timestamp = int(timestamp)

                batch.append((name, value, timestamp))

            self.middleware.call_sync("reporting.push_graphite_queues", batch)


class GraphiteEventSource(EventSource):
    """
    Proxies collectd data. Available options:
    * `reporting.graphite` - all data
    * `reporting.graphite:include,cpu-.*,disk-.*` - only include CPU and disk data
    * `reporting.graphite:exclude,cpu-.*,disk-.*` - all data except disk and CPU
    """
    def run_sync(self):
        mode = None
        names = []
        if self.arg:
            mode, names = self.arg.split(",", 1)

            if mode not in ["include", "exclude"]:
                raise ValueError(f"Invalid mode: {mode!r}")

            names = [re.compile(r) for r in names.split(",")]

        queue = Queue(1024)
        self.middleware.call_sync("reporting.register_graphite_queue", queue)
        try:
            self._run(mode, names, queue)
        finally:
            self.middleware.call_sync("reporting.unregister_graphite_queue", queue)

    def _run(self, mode, names, queue):
        while not self._cancel_sync.is_set():
            items = []
            for name, value, timestamp in queue.get():
                if self._accept(mode, names, name):
                    items.append([name, value, timestamp])

            if items:
                self.send_event("ADDED", fields={"items": items})

    def _accept(self, mode, names, name):
        if mode is None:
            return True

        if mode == "include":
            return any(r.match(name) for r in names)

        if mode == "exclude":
            return all(not r.match(name) for r in names)


class ReportingService(Service):
    has_server = False
    lock = asyncio.Lock()
    queues = []
    server = None
    server_shutdown_timer = None

    @private
    async def has_internal_graphite_server(self):
        return self.has_server

    @private
    async def register_graphite_queue(self, queue):
        async with self.lock:
            if self.server_shutdown_timer is not None:
                self.middleware.logger.debug("Canceling internal Graphite server shutdown")
                self.server_shutdown_timer.cancel()
                self.server_shutdown_timer = None

            self.queues.append(queue)

            if self.server is None:
                self.middleware.logger.debug("Starting internal Graphite server")
                GraphiteHandler.middleware = self.middleware
                self.server = GraphiteServer(("127.0.0.1", 2003), GraphiteHandler)
                start_daemon_thread(target=self.server.serve_forever)
                self.has_server = True
                await self.middleware.call("service.restart", "collectd")

    @private
    async def unregister_graphite_queue(self, queue):
        async with self.lock:
            self.queues.remove(queue)

            if not self.queues:
                self.middleware.logger.debug("Scheduling internal Graphite server shutdown")
                self.server_shutdown_timer = asyncio.get_event_loop().call_later(
                    300,
                    lambda: asyncio.ensure_future(self.middleware.call("reporting.shutdown_graphite_server")),
                )

    @private
    async def shutdown_graphite_server(self):
        async with self.lock:
            self.middleware.logger.debug("Shutting down internal Graphite server")

            self.has_server = False
            await self.middleware.call("service.restart", "collectd")

            await self.middleware.run_in_thread(self.server.shutdown)
            self.server = None
            self.server_shutdown_timer = None

            self.middleware.logger.debug("Internal Graphite server shut down successfully")

    @private
    async def push_graphite_queues(self, batch):
        for queue in list(self.queues):
            try:
                queue.put(batch)
            except Full:
                pass


async def setup(middleware):
    middleware.register_event_source("reporting.graphite", GraphiteEventSource)
