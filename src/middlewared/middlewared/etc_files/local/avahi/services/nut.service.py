from middlewared.plugins.etc import FileShouldNotExist
from middlewared.utils import mdns


def render(service, middleware, render_ctx):

    conf = render_ctx['ups.config']
    if not render_ctx['ups.service.started_or_enabled']:
        raise FileShouldNotExist()

    try:
        return mdns.generate_avahi_srv_record('NUT', custom_port=conf.remoteport)
    except Exception:
        middleware.logger.error(
            'Failed to generate mDNS SRV record for the nut service',
            exc_info=True
        )

    raise FileShouldNotExist()
