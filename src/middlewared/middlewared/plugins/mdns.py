from middlewared.service import Service, private, accepts
from middlewared.service_exception import CallError
from middlewared.utils import run


class mDNSAdvertiseService(Service):
    @private
    async def start(self):
        avahi = await run(['service', 'avahi-daemon', 'onestart'], check=False)
        if avahi.returncode != 0:
            raise CallError(
                f'Failed to start avahi daemon: [{avahi.stderr.decode()}]'
            )

    @private
    async def stop(self):
        avahi = await run(['service', 'avahi-daemon', 'onestop'], check=False)
        if avahi.returncode != 0:
            raise CallError(
                f'Failed to stop avahi daemon: [{avahi.stderr.decode()}]'
            )

    @private
    async def restart(self):
        await self.stop()
        await self.start()

    @accepts()
    async def reload(self):
        """
        Regenerate and reload mDNS configuration.
        """
        await self.middleware.call('etc.generate', 'mdns')
        avahi = await run(['service', 'avahi-daemon', 'reload'], check=False)
        if avahi.returncode != 0:
            raise CallError(
                f'Failed to reload avahi daemon: [{avahi.stderr.decode()}]'
            )
