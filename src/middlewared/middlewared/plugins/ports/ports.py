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

    async def get_in_use(self):
        # TODO: Remove either this or the above one probably
        ports = []
        for delegate in self.DELEGATES:
            used_ports = await delegate.get_ports()
            if used_ports:
                ports.append({
                    'type': delegate.title,
                    'ports': used_ports,
                })

        return ports
