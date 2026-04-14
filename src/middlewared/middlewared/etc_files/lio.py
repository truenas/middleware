from middlewared.utils.lio.config import write_lio_config


def render(service, middleware, render_ctx):
    write_lio_config(render_ctx)
