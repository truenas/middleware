from truenas_pymdns.server.config import ServiceConfig, generate_service_config

from middlewared.plugins.etc import FileShouldNotExist
from middlewared.utils.mdns import ip_addresses_to_interface_names


def render(service, middleware, render_ctx):
    if render_ctx['failover.status'] not in ('SINGLE', 'MASTER'):
        raise FileShouldNotExist()

    conf = render_ctx['system.general.config']
    interfaces: list[str] = []
    if conf['ui_address'][0] != '0.0.0.0':
        interfaces = ip_addresses_to_interface_names(
            render_ctx['interface.query'], conf['ui_address'],
        )

    try:
        cfg = ServiceConfig(
            service_type='_http._tcp',
            port=int(conf['ui_port']),
            interfaces=interfaces,
        )
        return generate_service_config(cfg)
    except Exception:
        middleware.logger.error(
            'Failed to generate HTTP discovery service config',
            exc_info=True,
        )
        raise FileShouldNotExist()
