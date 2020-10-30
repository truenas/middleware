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

    async def run(self):
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
                self.middleware.logger.error("Unhandled exception in iscsi.host.injection.run", exc_info=True)

            await asyncio.sleep(5)

    def collect(self):
        hosts = set()

        targets_path = "/sys/kernel/scst_tgt/targets/iscsi"
        for target in os.listdir(targets_path):
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
    asyncio.ensure_future(middleware.call("iscsi.host.injection.run"))
