from middlewared.plugins.truenas_s3.render import render_credentials


def render(service, middleware):
    data = middleware.call_sync("s3.render_data")
    for key in data["accesskeys"]:
        if key["status"] == "USER_MISSING" and not key["local"]:
            # a directory services account that does not resolve right now
            # may just be a directory that is not answering; the key renders
            # disabled until the next render finds the account again
            middleware.logger.warning(
                "s3: access key %s belongs to a directory services account that does not resolve, rendered disabled",
                key["access_key"],
            )
    return render_credentials(data["accesskeys"])
