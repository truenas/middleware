from middlewared.utils.lio.config import teardown_lio_config, write_lio_config


def render(service, middleware, render_ctx):
    if not middleware.call_sync("iscsi.global.lio_enabled"):
        teardown_lio_config()
        return
    if render_ctx.get("failover.node") in ("A", "B"):
        render_ctx["failover.local_ip"] = middleware.call_sync("failover.local_ip")
        render_ctx["failover.remote_ip"] = middleware.call_sync("failover.remote_ip")
    else:
        render_ctx["failover.local_ip"] = ""
        render_ctx["failover.remote_ip"] = ""

    write_lio_config(render_ctx)
