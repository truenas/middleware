from middlewared.common.ports import ServicePortDelegate


class FTPServicePortDelegate(ServicePortDelegate):

    name = 'FTP'
    namespace = 'ftp'
    port_fields = ['port']
    title = 'FTP Service'


async def setup(middleware):
    await middleware.call('port.register_attachment_delegate', FTPServicePortDelegate(middleware))
