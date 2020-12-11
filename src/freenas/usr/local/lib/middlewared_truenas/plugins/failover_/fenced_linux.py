import subprocess

from middlewared.service import Service


class FencedForceService(Service):

    class Config:
        private = True
        namespace = 'failover.fenced'

    def start(self, force=False):

        # get the boot disks so fenced doesn't try to
        # place reservations on the boot drives
        boot_disks = ""
        try:
            boot_disks = ",".join(self.middleware.call_sync('boot.get_disks'))
        except Exception:
            self.middleware.logger.warning(
                'Failed to get boot disks for fenced', exc_info=True
            )
            # just because we can't grab the boot disks from middleware
            # doesn't mean we should fail to start fenced since it
            # (ultimately) prevents data corruption on HA systems
            pass

        # build the shell command include the "force" option
        # if requested
        cmd = ['fenced', '-ed', boot_disks]
        if force:
            cmd.append('-f')

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out, err = proc.communicate()

        return proc.returncode

    def stop(self):

        subprocess.run(['pkill', '-9', '-f', 'fenced'])
