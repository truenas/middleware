from middlewared.common.ports import ServicePortDelegate


class SMBServicePortDelegate(ServicePortDelegate):

    name = 'smb'
    namespace = 'smb'
    title = 'SMB Service'

    async def get_ports_internal(self):
        return [137, 138, 139, 445]


async def setup(middleware):
    await middleware.call('port.register_attachment_delegate', SMBServicePortDelegate(middleware))
