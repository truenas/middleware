from truenas_pymdns.server.config import ServiceConfig, generate_service_config

from middlewared.plugins.etc import FileShouldNotExist


def render(service, middleware, render_ctx):
    if render_ctx["failover.status"] not in ("SINGLE", "MASTER"):
        raise FileShouldNotExist()

    if not render_ctx["ups.service.started_or_enabled"]:
        raise FileShouldNotExist()

    conf = render_ctx["ups.config"]
    try:
        cfg = ServiceConfig(
            service_type="_nut._tcp",
            port=int(conf.remoteport),
        )
        return generate_service_config(cfg)
    except Exception:
        middleware.logger.error(
            "Failed to generate NUT discovery service config",
            exc_info=True,
        )
        raise FileShouldNotExist()
