import copy

from middlewared.service import Service


class PortService(Service):

    DELEGATES = {}
    SYSTEM_USED_PORTS = [
        {'type': 'System', 'ports': [6000]},
    ]

    class Config:
        private = True

    async def register_attachment_delegate(self, delegate):
        self.DELEGATES[delegate.namespace] = delegate

    async def get_used_ports(self):
        ports = []
        for delegate in self.DELEGATES:
            ports.extend(await delegate.get_ports())
        return ports

    async def get_in_use(self):
        # TODO: Remove either this or the above one probably
        ports = copy.deepcopy(self.SYSTEM_USED_PORTS)
        for delegate in self.DELEGATES.values():
            used_ports = await delegate.get_ports()
            if used_ports:
                ports.append({
                    'namespace': delegate.namespace,
                    'type': delegate.title,
                    'ports': used_ports,
                })

        return ports
