from middlewared.common.ports import ServicePortDelegate


class WebdavServicePortDelegate(ServicePortDelegate):

    name = 'webdav'
    namespace = 'webdav'
    port_fields = ['tcpport', 'tcpportssl']
    title = 'Webdav Service'


async def setup(middleware):
    await middleware.call('port.register_attachment_delegate', WebdavServicePortDelegate(middleware))
