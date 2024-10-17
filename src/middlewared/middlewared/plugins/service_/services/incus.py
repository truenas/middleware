import os
import re
import signal

from pystemd.systemd1 import Unit

from middlewared.plugins.service_.services.base import SimpleService


RE_DNSMASQ_PID = re.compile(r'^pid: (\d+)', flags=re.M)


class IncusService(SimpleService):
    name = "incus"

    etc = ["subids"]
    systemd_unit = "incus"

    async def stop(self):
        await self._unit_action("Stop")
        # incus.socket needs to be stopped in addition to the service
        unit = Unit("incus.socket")
        unit.load()
        await self._unit_action("Stop", unit=unit)

        # Incus will run dnsmasq for its managed network and not stop it
        # when the service is stopped.
        dnsmasq_pid = '/var/lib/incus/networks/incusbr0/dnsmasq.pid'
        if os.path.exists(dnsmasq_pid):
            try:
                with open(dnsmasq_pid) as f:
                    data = f.read()
                    if reg := RE_DNSMASQ_PID.search(data):
                        # os.kill should never block, will this still require a thread?
                        os.kill(int(reg.group(1)), signal.SIGTERM)
            except FileNotFoundError:
                pass
