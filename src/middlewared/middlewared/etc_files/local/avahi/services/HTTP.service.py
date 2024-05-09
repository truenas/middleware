from middlewared.plugins.etc import FileShouldNotExist
from middlewared.utils import mdns


def render(service, middleware, render_ctx):

    conf = render_ctx['system.general.config']
    if conf['ui_address'][0] != '0.0.0.0':
        iindexes = mdns.ip_addresses_to_interface_indexes(
            render_ctx['interface.query'], conf['ui_address']
        )
    else:
        iindexes = None

    try:
        return mdns.generate_avahi_srv_record(
            'HTTP', iindexes, custom_port=conf['ui_port']
        )
    except Exception:
        middleware.logger.error(
            'Failed to generate mDNS SRV record for the HTTP service',
            exc_info=True
        )

    raise FileShouldNotExist()
