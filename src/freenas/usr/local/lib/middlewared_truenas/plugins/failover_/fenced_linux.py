import subprocess

from middlewared.service import Service


class FencedForceService(Service):

    class Config:
        private = True
        namespace = 'failover.fenced'

    def start(self):

        # TODO
        # Return False always until fenced daemon
        # can be written to work on Linux.
        return False

    def force(self):

        return False

    def stop(self):

        subprocess.run(['pkill', '-9', '-f', 'fenced'])
