from middlewared.plugins.truenas_s3.render import render_buckets

MISSING_ALERT = "S3BucketDatasetMissing"


def render(service, middleware):
    data = middleware.call_sync("s3.render_data")

    # every enabled bucket renders unconditionally: the daemon excludes a
    # row it cannot mount and answers 503 for it, which is the honest
    # answer for a dataset that vanished or moved outside middleware. The
    # alert is what tells the operator
    for bucket in data["buckets"]:
        args = {"id": bucket["id"], "name": bucket["name"], "dataset": bucket["dataset"]}
        gone = bucket["enabled"] and (
            bucket["dataset_missing"] or (bucket["live_mountpoint"] and bucket["live_mountpoint"] != bucket["path"])
        )
        if gone:
            middleware.call_sync("alert.oneshot_create", MISSING_ALERT, args)
        else:
            middleware.call_sync("alert.oneshot_delete", MISSING_ALERT, bucket["id"])

    return render_buckets(data["config"], data["buckets"], data["audit_licensed"])
