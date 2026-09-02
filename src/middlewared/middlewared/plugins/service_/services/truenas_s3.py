import os

from middlewared.plugins.truenas_s3.lifecycle import daemon_reload

from .base import SimpleService

PAM_STACK = "/etc/pam.d/truenas-s3"


class TrueNASS3Service(SimpleService):
    name = "truenas_s3"
    etc = ["truenas_s3"]
    reloadable = True
    restartable = True
    may_run_on_standby = False
    systemd_unit = "truenas_s3"

    async def before_start(self):
        # the account gate's PAM stack belongs to the pam group, which boot
        # and directory service changes render; a first start on a system
        # upgraded in place must not find it missing
        if not await self.middleware.run_in_thread(os.path.exists, PAM_STACK):
            await self.middleware.call("etc.generate", "pam")
        # the listen address lives in a unit drop-in the etc group has just
        # rendered; systemd only reads it again after a daemon-reload
        await self.middleware.run_in_thread(daemon_reload)

    async def before_restart(self):
        await self.middleware.run_in_thread(daemon_reload)
