from middlewared.common.ports import ServicePortDelegate


class SystemGeneralServicePortDelegate(ServicePortDelegate):

    name = 'webui'
    port_fields = ['ui_port', 'ui_httpsport']
    service = 'system.general'
    title = 'WebUI Service'


async def setup(middleware):
    await middleware.call('port.register_attachment_delegate', SystemGeneralServicePortDelegate(middleware))
