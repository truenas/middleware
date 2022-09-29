from middlewared.service import Service


class PortService(Service):

    DELEGATES = []

    class Config:
        private = True

    async def register_attachment_delegate(self, delegate):
        self.DELEGATES.append(delegate)

    async def get_used_ports(self):
        ports = []
        for delegate in self.DELEGATES:
            ports.extend(await delegate.get_ports())
        return ports
