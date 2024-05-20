from middlewared.plugins.etc import FileShouldNotExist
from middlewared.utils import mdns


def render(service, middleware, render_ctx):

    conf = render_ctx['smb.config']
    if not render_ctx['service.started_or_enabled']:
        raise FileShouldNotExist()

    if conf['bindip']:
        iindexes = mdns.ip_addresses_to_interface_indexes(
            render_ctx['interface.query'], conf['bindip']
        )
    else:
        iindexes = None

    try:
        return mdns.generate_avahi_srv_record('SMB', iindexes)
    except Exception:
        middleware.logger.error(
            'Failed to generate mDNS SRV record for the SMB service',
            exc_info=True
        )

    raise FileShouldNotExist()
