from middlewared.alert.base import Alert, AlertCategory, AlertClass, AlertLevel, OneShotAlertClass


class S3BucketDatasetMissingAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False
    level = AlertLevel.WARNING
    category = AlertCategory.SHARING
    title = "S3 Bucket Dataset Is Missing"
    text = (
        'S3 bucket "%(name)s" is unavailable because its dataset %(dataset)s no longer exists. Restore the dataset, '
        "or delete and recreate the bucket."
    )

    async def create(self, args):
        return Alert(S3BucketDatasetMissingAlertClass, args, key=args["id"])

    async def delete(self, alerts, query):
        return list(filter(lambda alert: alert.key != str(query), alerts))
