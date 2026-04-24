from middlewared.utils.lio.config import write_lio_config


def render(service, middleware, render_ctx):
    if render_ctx.get('failover.node') in ('A', 'B'):
        render_ctx['failover.local_ip'] = middleware.call_sync('failover.local_ip')
        render_ctx['failover.remote_ip'] = middleware.call_sync('failover.remote_ip')
    else:
        render_ctx['failover.local_ip'] = ''
        render_ctx['failover.remote_ip'] = ''

    write_lio_config(render_ctx)
