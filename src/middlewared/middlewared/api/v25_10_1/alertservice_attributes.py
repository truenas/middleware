from typing import Annotated, Literal, Union

from pydantic import Discriminator, Field, Secret

from middlewared.api.base import BaseModel, HttpUrl, NonEmptyString, TcpPort

__all__ = ["AlertServiceAttributes"]


class AWSSNSServiceModel(BaseModel):
    type: Literal["AWSSNS"]
    """Alert service type identifier for Amazon SNS."""
    region: NonEmptyString
    """AWS region where the SNS topic is located."""
    topic_arn: NonEmptyString
    """Amazon Resource Name (ARN) of the SNS topic to publish alerts to."""
    aws_access_key_id: NonEmptyString
    """AWS access key ID for authentication."""
    aws_secret_access_key: Secret[NonEmptyString]
    """AWS secret access key for authentication."""


class InfluxDBServiceModel(BaseModel):
    type: Literal["InfluxDB"]
    """Alert service type identifier for InfluxDB."""
    host: NonEmptyString
    """InfluxDB server hostname or IP address."""
    username: NonEmptyString
    """Username for InfluxDB authentication."""
    password: Secret[NonEmptyString]
    """Password for InfluxDB authentication."""
    database: NonEmptyString
    """InfluxDB database name to store alert data."""
    series_name: NonEmptyString
    """Name of the time series to store alert events."""


class MailServiceModel(BaseModel):
    type: Literal["Mail"]
    """Alert service type identifier for email notifications."""
    email: str = ""
    """Email address to send alerts to. Empty string uses system default."""


class MattermostServiceModel(BaseModel):
    type: Literal["Mattermost"]
    """Alert service type identifier for Mattermost."""
    url: Secret[HttpUrl]
    """Mattermost webhook URL for posting alerts."""
    username: NonEmptyString
    """Username to display when posting alerts to Mattermost."""
    channel: str = ""
    """Mattermost channel name to post alerts to. Empty string uses webhook default."""
    icon_url: Literal[""] | HttpUrl = ""
    """URL of icon image to display with alert messages. Empty string uses default."""


class OpsGenieServiceModel(BaseModel):
    type: Literal["OpsGenie"]
    """Alert service type identifier for OpsGenie."""
    api_key: Secret[NonEmptyString]
    """OpsGenie API key for authentication."""
    api_url: Literal[""] | HttpUrl = ""
    """OpsGenie API URL. Empty string uses default OpsGenie endpoint."""


class PagerDutyServiceModel(BaseModel):
    type: Literal["PagerDuty"]
    """Alert service type identifier for PagerDuty."""
    service_key: Secret[NonEmptyString]
    """PagerDuty service integration key for sending alerts."""
    client_name: NonEmptyString
    """Client name to identify the source of alerts in PagerDuty."""


class SlackServiceModel(BaseModel):
    type: Literal["Slack"]
    """Alert service type identifier for Slack."""
    url: Secret[HttpUrl]
    """Slack webhook URL for posting alert messages."""


class SNMPTrapServiceModel(BaseModel):
    type: Literal["SNMPTrap"]
    """Alert service type identifier for SNMP traps."""
    host: str
    """SNMP trap receiver hostname or IP address."""
    port: TcpPort
    """TCP port number for SNMP trap receiver."""
    v3: bool
    """Whether to use SNMP v3 instead of v1/v2c."""
    # v1/v2
    community: NonEmptyString | None = None
    """SNMP community string for v1/v2c authentication or `null` for v3."""
    # v3
    v3_username: NonEmptyString | None = None
    """SNMP v3 username for authentication or `null` for v1/v2c."""
    v3_authkey: Secret[NonEmptyString | None] = None
    """SNMP v3 authentication key or `null` if not using authentication."""
    v3_privkey: Secret[NonEmptyString | None] = None
    """SNMP v3 privacy key for encryption or `null` if not using privacy."""
    v3_authprotocol: Literal[None, "MD5", "SHA", "128SHA224", "192SHA256", "256SHA384", "384SHA512"] = None
    """SNMP v3 authentication protocol or `null` for no authentication."""
    v3_privprotocol: Literal[None, "DES", "3DESEDE", "AESCFB128", "AESCFB192", "AESCFB256", "AESBLUMENTHALCFB192",
                             "AESBLUMENTHALCFB256"] = None
    """SNMP v3 privacy protocol for encryption or `null` for no privacy."""


class TelegramServiceModel(BaseModel):
    type: Literal["Telegram"]
    """Alert service type identifier for Telegram."""
    bot_token: Secret[NonEmptyString]
    """Telegram bot token for API authentication."""
    chat_ids: list[int] = Field(min_length=1)
    """List of Telegram chat IDs to send alerts to (minimum 1 required)."""


class VictorOpsServiceModel(BaseModel):
    type: Literal["VictorOps"]
    """Alert service type identifier for VictorOps (now Splunk On-Call)."""
    api_key: Secret[NonEmptyString]
    """VictorOps API key for authentication."""
    routing_key: NonEmptyString
    """VictorOps routing key to determine alert destination and escalation policy."""


AlertServiceAttributes = Annotated[
    Union[
        AWSSNSServiceModel,
        InfluxDBServiceModel,
        MailServiceModel,
        MattermostServiceModel,
        OpsGenieServiceModel,
        PagerDutyServiceModel,
        SlackServiceModel,
        SNMPTrapServiceModel,
        TelegramServiceModel,
        VictorOpsServiceModel
    ],
    Discriminator("type"),
]
