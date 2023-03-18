from middlewared.common.ports import ServicePortDelegate


class SystemGeneralServicePortDelegate(ServicePortDelegate):

    bind_address_field = 'ui_address'
    name = 'webui'
    namespace = 'system.general'
    port_fields = ['ui_port', 'ui_httpsport']
    title = 'WebUI Service'


async def setup(middleware):
    await middleware.call('port.register_attachment_delegate', SystemGeneralServicePortDelegate(middleware))
