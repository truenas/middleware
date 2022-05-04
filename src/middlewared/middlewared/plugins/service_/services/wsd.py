from .base import SimpleService, ServiceState


class WSDService(SimpleService):
    name = "wsdd"
    etc = ["wsd"]
    freebsd_rc = "wsdd"

    async def _get_state_freebsd(self):
        stdout = (await self._freebsd_service("wsdd", "status")).stdout
        running = 'wsdd running as pid' in stdout
        pid = [] if not running else stdout.split('wsdd running as pid')[1].strip()
        return ServiceState(running, pid)
