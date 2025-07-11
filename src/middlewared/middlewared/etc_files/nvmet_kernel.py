from middlewared.utils.nvmet.kernel import write_config


def render(service, middleware, render_ctx):
    write_config(render_ctx)
