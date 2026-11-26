from truenas_pymdns.server.config import ServiceConfig, generate_service_config

from middlewared.plugins.etc import FileShouldNotExist
from middlewared.utils.mdns import ip_addresses_to_interface_names

# Lets clients such as the TrueNAS Connect app find a TrueNAS whatever its
# host name: its web UI on the HTTPS port, with what /api/versions and
# auth.mechanism_choices answer before signing in.


def render(service, middleware, render_ctx):
    if render_ctx["failover.status"] not in ("SINGLE", "MASTER"):
        raise FileShouldNotExist()

    conf = render_ctx["system.general.config"]
    interfaces: list[str] = []
    if conf["ui_address"][0] != "0.0.0.0":
        interfaces = ip_addresses_to_interface_names(
            render_ctx["interface.query"],
            conf["ui_address"],
        )

    api_versions = middleware.public_api_versions
    try:
        cfg = ServiceConfig(
            service_type="_truenas-api._tcp",
            port=int(conf["ui_httpsport"]),
            interfaces=interfaces,
            txt={
                "txtvers": "1",
                "api": f"min={api_versions[0]},max={api_versions[-1]}",
                "mech": ",".join(m.removesuffix("_PLAIN") for m in render_ctx["auth.mechanism_choices"]),
            },
        )
        return generate_service_config(cfg)
    except Exception:
        middleware.logger.error(
            "Failed to generate TRUENAS_API discovery service config",
            exc_info=True,
        )
        raise FileShouldNotExist()
