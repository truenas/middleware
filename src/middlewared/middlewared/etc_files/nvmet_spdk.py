from middlewared.utils.nvmet.spdk import inject_path_to_recordsize, write_config


def render(service, middleware, render_ctx):
    if middleware.call_sync('nvmet.spdk.nvmf_ready', True):
        inject_path_to_recordsize(middleware, render_ctx)
        write_config(render_ctx)
