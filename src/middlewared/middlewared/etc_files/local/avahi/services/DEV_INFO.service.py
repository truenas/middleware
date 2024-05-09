from middlewared.plugins.etc import FileShouldNotExist
from middlewared.utils import mdns


def render(service, middleware, render_ctx):

    try:
        return mdns.generate_avahi_srv_record(
            'DEV_INFO', txt_records=[f'model={mdns.DevType.MACPRORACK}']
        )
    except Exception:
        middleware.logger.error(
            'Failed to generate mDNS SRV record for the DEV_INFO service',
            exc_info=True
        )

    raise FileShouldNotExist()
