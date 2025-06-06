from middlewared.plugins.nvmet.spdk import write_config


def render(service, middleware, render_ctx):
    if middleware.call_sync('nvmet.spdk.nvmf_ready', True):
        write_config(render_ctx)
