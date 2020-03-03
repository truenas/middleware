import logging

from middlewared.utils import osc

from .base_freebsd import SimpleServiceFreeBSD
from .base_linux import SimpleServiceLinux
from .base_state import ServiceState  # noqa

logger = logging.getLogger(__name__)


class ServiceInterface:
    name = NotImplemented

    etc = []
    restartable = False  # Implements `restart` method instead of `stop` + `start`
    reloadable = False  # Implements `reload` method

    def __init__(self, middleware):
        self.middleware = middleware

    async def get_state(self):
        raise NotImplementedError

    async def start(self):
        raise NotImplementedError

    async def before_start(self):
        pass

    async def after_start(self):
        pass

    async def stop(self):
        raise NotImplementedError

    async def before_stop(self):
        pass

    async def after_stop(self):
        pass

    async def restart(self):
        raise NotImplementedError

    async def before_restart(self):
        pass

    async def after_restart(self):
        pass

    async def reload(self):
        raise NotImplementedError

    async def before_reload(self):
        pass

    async def after_reload(self):
        pass


class IdentifiableServiceInterface:
    async def identify(self, procname):
        raise NotImplementedError


class SimpleService(ServiceInterface, IdentifiableServiceInterface, SimpleServiceLinux, SimpleServiceFreeBSD):
    async def get_state(self):
        if osc.IS_LINUX:
            return await self._get_state_linux()
        else:
            return await self._get_state_freebsd()

    async def start(self):
        if osc.IS_LINUX:
            return await self._start_linux()
        else:
            return await self._start_freebsd()

    async def stop(self):
        if osc.IS_LINUX:
            return await self._stop_linux()
        else:
            return await self._stop_freebsd()

    async def restart(self):
        if osc.IS_LINUX:
            return await self._restart_linux()
        else:
            return await self._restart_freebsd()

    async def reload(self):
        if osc.IS_LINUX:
            return await self._reload_linux()
        else:
            return await self._reload_freebsd()

    async def identify(self, procname):
        if osc.IS_LINUX:
            return await self._identify_linux(procname)
        else:
            return await self._identify_freebsd(procname)
