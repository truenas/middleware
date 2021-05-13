import contextlib
import os
import textwrap

from middlewared.service import private, Service


class SMBService(Service):

    class Config:
        service = 'cifs'
        service_verb = 'restart'

    @private
    def set_timemachine_quotas(self):
        for share in self.middleware.call_sync("sharing.smb.query", [("locked", "=", False), ("enabled", "=", True)]):
            self.set_timemachine_quota(share)
    
    @private
    def set_timemachine_quota(self, share):
        timemachine_supported_path = os.path.join(share["path"], ".com.apple.timemachine.supported")
        timemachine_quota_plist_path = os.path.join(share["path"], ".com.apple.TimeMachine.quota.plist")
        timemachine_quota_plist_managed_flag = os.path.join(share["path"],
                                                            ".com.apple.TimeMachine.quota.plist.FreeNAS-managed")
        if share["timemachine"] and share["timemachine_quota"]:
            with contextlib.suppress(IOError):
                with open(timemachine_supported_path, "w"):
                    pass

            with contextlib.suppress(IOError):
                with open(timemachine_quota_plist_path, "w") as f:
                    f.write(textwrap.dedent("""\
                        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
                        <plist version="1.0">
                            <dict>
                                <key>GlobalQuota</key>
                                <integer>%d</integer>
                            </dict>
                        </plist>
                    """ % (share["timemachine_quota"] * 1024 * 1024 * 1024)))

            with contextlib.suppress(IOError):
                with open(timemachine_quota_plist_managed_flag, "w") as f:
                    pass

            with contextlib.suppress(IOError):
                stat = os.stat(share["path"])
                os.chmod(timemachine_supported_path, 0o644)
                os.chown(timemachine_supported_path, stat.st_uid, stat.st_gid)
                os.chmod(timemachine_quota_plist_path, 0o644)
                os.chown(timemachine_quota_plist_path, stat.st_uid, stat.st_gid)
                os.chmod(timemachine_quota_plist_managed_flag, 0o644)
                os.chown(timemachine_quota_plist_managed_flag, stat.st_uid, stat.st_gid)
        else:
            if os.path.exists(timemachine_quota_plist_managed_flag):
                with contextlib.suppress(IOError):
                    os.unlink(timemachine_supported_path)

                with contextlib.suppress(IOError):
                    os.unlink(timemachine_quota_plist_path)
