import subprocess

import sysctl

from middlewared.service import private, Service


class NFSService(Service):

    class Config:
        service = "nfs"
        service_verb = "restart"
        datastore_prefix = "nfs_srv_"
        datastore_extend = 'nfs.nfs_extend'

    @private
    def setup_v4(self):
        config = self.middleware.call_sync("nfs.config")

        if config["v4_krb_enabled"]:
            subprocess.run(["service", "gssd", "onerestart"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(["service", "gssd", "forcestop"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        if config["v4"]:
            sysctl.filter("vfs.nfsd.server_max_nfsvers")[0].value = 4
            if config["v4_v3owner"]:
                # Per RFC7530, sending NFSv3 style UID/GIDs across the wire is now allowed
                # You must have both of these sysctl"s set to allow the desired functionality
                sysctl.filter("vfs.nfsd.enable_stringtouid")[0].value = 1
                sysctl.filter("vfs.nfs.enable_uidtostring")[0].value = 1
                subprocess.run(["service", "nfsuserd", "forcestop"], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
            else:
                sysctl.filter("vfs.nfsd.enable_stringtouid")[0].value = 0
                sysctl.filter("vfs.nfs.enable_uidtostring")[0].value = 0
                subprocess.run(["service", "nfsuserd", "onerestart"], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
        else:
            sysctl.filter("vfs.nfsd.server_max_nfsvers")[0].value = 3
            if config["userd_manage_gids"]:
                subprocess.run(["service", "nfsuserd", "onerestart"], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
            else:
                subprocess.run(["service", "nfsuserd", "forcestop"], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
