from middlewared.utils.lio.config import teardown_lio_config, write_lio_config


def render(service, middleware, render_ctx):
    if not middleware.call_sync("iscsi.global.lio_enabled"):
        teardown_lio_config()
        return
    write_lio_config(render_ctx)
