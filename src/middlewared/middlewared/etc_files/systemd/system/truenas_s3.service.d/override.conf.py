from middlewared.plugins.truenas_s3.render import render_unit_dropin


def render(service, middleware):
    config = middleware.call_sync("s3.config")
    return render_unit_dropin(config.model_dump())
