import asyncio
from collections import namedtuple
from ipaddress import ip_address
import os

from middlewared.service import Service

CollectedHost = namedtuple("CollectedHost", ["ip", "iqn"])


class iSCSIHostsInjectionService(Service):
    class Config:
        namespace = "iscsi.host.injection"
        private = True

    control_lock = asyncio.Lock()
    run_event = None
    stop_event = None

    async def start(self):
        async with self.control_lock:
            if self.run_event:
                self.logger.debug("iscsi.host.injection is already running")
                return

            self.logger.debug("Starting iscsi.host.injection")
            self.run_event = asyncio.Event()
            self.stop_event = asyncio.Event()
            asyncio.ensure_future(self._run(self.run_event, self.stop_event))

    async def stop(self):
        async with self.control_lock:
            if not self.run_event:
                self.logger.debug("iscsi.host.injection is already stopped")
                return

            self.logger.debug("Stopping iscsi.host.injection")
            self.run_event.set()
            await self.stop_event.wait()

            self.run_event = None
            self.stop_event = None

    async def _run(self, run_event, stop_event):
        try:
            while True:
                try:
                    await self.middleware.call(
                        "iscsi.host.batch_update",
                        [
                            dict(host._asdict(), added_automatically=True)
                            for host in await self.middleware.call("iscsi.host.injection.collect")
                        ],
                    )
                except Exception:
                    self.middleware.logger.error("Unhandled exception in iscsi.host.injection", exc_info=True)

                try:
                    await asyncio.wait_for(run_event.wait(), 5)
                    return
                except asyncio.TimeoutError:
                    continue
        finally:
            stop_event.set()

    def collect(self):
        hosts = set()

        targets_path = "/sys/kernel/scst_tgt/targets/iscsi"
        try:
            targets = os.listdir(targets_path)
        except FileNotFoundError:
            return hosts

        for target in targets:
            target_path = os.path.join(targets_path, target)
            if not os.path.isdir(target_path):
                continue

            sessions_path = os.path.join(target_path, "sessions")
            for session in os.listdir(sessions_path):
                if "#" not in session:
                    continue

                iqn, target_ip = session.split("#", 1)

                session_path = os.path.join(sessions_path, session)
                if not os.path.isdir(session_path):
                    continue

                for ip in os.listdir(session_path):
                    try:
                        ip_address(ip)
                    except ValueError:
                        continue

                    ip_path = os.path.join(session_path, ip)
                    if not os.path.isdir(ip_path):
                        continue

                    hosts.add(CollectedHost(ip, iqn))

        return hosts


async def setup(middleware):
    service = await middleware.call("service.query", [["service", "=", "iscsitarget"]], {"get": True})
    if service["enable"] or service["state"] == "RUNNING":
        await middleware.call("iscsi.host.injection.start")
