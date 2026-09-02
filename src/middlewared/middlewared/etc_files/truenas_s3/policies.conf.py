from middlewared.plugins.truenas_s3.render import render_policies


def render(service, middleware):
    data = middleware.call_sync("s3.render_data")
    return render_policies(data["config"], data["buckets"])
