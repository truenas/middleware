import boto3

from middlewared.alert.base import ThreadedAlertService
from middlewared.schema import Dict, Str


class AWSSNSAlertService(ThreadedAlertService):
    title = "AWS SNS"

    schema = Dict(
        "awssns_attributes",
        Str("region", required=True, empty=False),
        Str("topic_arn", required=True, empty=False),
        Str("aws_access_key_id", required=True, empty=False),
        Str("aws_secret_access_key", required=True, empty=False),
        strict=True,
    )

    def send_sync(self, alerts, gone_alerts, new_alerts):
        client = boto3.client(
            "sns",
            region_name=self.attributes["region"],
            aws_access_key_id=self.attributes["aws_access_key_id"],
            aws_secret_access_key=self.attributes["aws_secret_access_key"],
        )

        client.publish(
            TopicArn=self.attributes["topic_arn"],
            Subject="Alerts",
            Message=self._format_alerts(alerts, gone_alerts, new_alerts),
        )
