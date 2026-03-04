from __future__ import annotations

from typing import Any

import boto3

from middlewared.alert.base import Alert, ThreadedAlertService


class AWSSNSAlertService(ThreadedAlertService):
    title = "AWS SNS"

    def send_sync(self, alerts: list[Alert[Any]], gone_alerts: list[Alert[Any]], new_alerts: list[Alert[Any]]) -> None:
        client = boto3.client(
            "sns",
            region_name=self.attributes["region"],
            aws_access_key_id=self.attributes["aws_access_key_id"],
            aws_secret_access_key=self.attributes["aws_secret_access_key"],
        )

        client.publish(
            TopicArn=self.attributes["topic_arn"],
            Subject="Alerts",
            Message=self._format_alerts_sync(alerts, gone_alerts, new_alerts),
        )
