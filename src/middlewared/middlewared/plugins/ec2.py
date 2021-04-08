import requests

from middlewared.service import Service


class EC2Service(Service):
    class Config:
        private = True

    def instance_id(self):
        r = requests.get("http://169.254.169.254/latest/meta-data/instance-id", timeout=10)
        r.raise_for_status()
        return r.text

    def setup(self):
        for key, func in [
            ("ec2:root_ssh_public_key_set", self.set_root_ssh_public_key),
            ("ec2:ntp_servers_set", self.set_ntp_servers),
        ]:
            if not self.middleware.call_sync("keyvalue.has_key", key):
                try:
                    func()
                except Exception:
                    self.logger.error("Error running %s", key, exc_info=True)
                else:
                    self.middleware.call_sync("keyvalue.set", key, True)

    def set_root_ssh_public_key(self):
        r = requests.get("http://169.254.169.254/1.0/meta-data/public-keys/0/openssh-key", timeout=10)
        r.raise_for_status()
        openssh_key = r.text

        root = self.middleware.call_sync("user.query", [["username", "=", "root"]], {"get": True})
        self.middleware.call_sync("user.update", root["id"], {
            "sshpubkey": openssh_key,
        })

    def set_ntp_servers(self):
        for server in self.middleware.call_sync("system.ntpserver.query"):
            self.middleware.call_sync("system.ntpserver.delete", server["id"])

        self.middleware.call_sync("system.ntpserver.create", {"address": "169.254.169.123"})


async def _event_system(middleware, event_type, args):
    if args["id"] == "ready":
        await middleware.call("boot.expand")
        await middleware.call("ec2.setup")


async def setup(middleware):
    if await middleware.call("system.environment") == "EC2":
        middleware.event_subscribe("system", _event_system)
