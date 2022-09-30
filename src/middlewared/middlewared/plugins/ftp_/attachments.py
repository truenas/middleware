from middlewared.common.ports import ServicePortDelegate


class FTPServicePortDelegate(ServicePortDelegate):

    name = 'FTP'
    port_fields = ['port']
    service = 'ftp'
    title = 'FTP Service'


async def setup(middleware):
    await middleware.call('port.register_attachment_delegate', FTPServicePortDelegate(middleware))
