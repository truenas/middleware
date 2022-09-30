from middlewared.common.ports import ServicePortDelegate


class FTPServicePortDelegate(ServicePortDelegate):

    port_fields = ['port']
    service = 'ftp'


async def setup(middleware):
    await middleware.call('port.register_attachment_delegate', FTPServicePortDelegate(middleware))
