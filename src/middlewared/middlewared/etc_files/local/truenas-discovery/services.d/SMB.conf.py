from truenas_pymdns.server.config import ServiceConfig, generate_service_config

from middlewared.plugins.etc import FileShouldNotExist
from middlewared.utils.mdns import ip_addresses_to_interface_names


def render(service, middleware, render_ctx):
    if render_ctx["failover.status"] not in ("SINGLE", "MASTER"):
        raise FileShouldNotExist()

    if not render_ctx["service.started_or_enabled"]:
        raise FileShouldNotExist()

    smb_config = render_ctx["smb.config"]
    interfaces: list[str] = []
    if smb_config["bindip"]:
        interfaces = ip_addresses_to_interface_names(
            render_ctx["interface.query"], smb_config["bindip"],
        )

    try:
        cfg = ServiceConfig(
            service_type="_smb._tcp",
            port=445,
            interfaces=interfaces,
        )
        return generate_service_config(cfg)
    except Exception:
        middleware.logger.error(
            "Failed to generate SMB discovery service config",
            exc_info=True,
        )
        raise FileShouldNotExist()
