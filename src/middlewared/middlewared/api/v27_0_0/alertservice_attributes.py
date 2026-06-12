from typing import Annotated, Literal, Union

from pydantic import Discriminator, Field, Secret

from middlewared.api.base import BaseModel, HttpUrl, NonEmptyString, TcpPort

__all__ = ["AlertServiceAttributes"]


class AWSSNSServiceModel(BaseModel):
    type: Literal["AWSSNS"] = Field(description="Alert service type identifier for Amazon SNS.")
    region: NonEmptyString = Field(description="AWS region where the SNS topic is located.")
    topic_arn: NonEmptyString = Field(description="Amazon Resource Name (ARN) of the SNS topic to publish alerts to.")
    aws_access_key_id: NonEmptyString = Field(description="AWS access key ID for authentication.")
    aws_secret_access_key: Secret[NonEmptyString] = Field(description="AWS secret access key for authentication.")


class InfluxDBServiceModel(BaseModel):
    type: Literal["InfluxDB"] = Field(description="Alert service type identifier for InfluxDB.")
    host: NonEmptyString = Field(description="InfluxDB server hostname or IP address.")
    username: NonEmptyString = Field(description="Username for InfluxDB authentication.")
    password: Secret[NonEmptyString] = Field(description="Password for InfluxDB authentication.")
    database: NonEmptyString = Field(description="InfluxDB database name to store alert data.")
    series_name: NonEmptyString = Field(description="Name of the time series to store alert events.")


class MailServiceModel(BaseModel):
    type: Literal["Mail"] = Field(description="Alert service type identifier for email notifications.")
    email: str = Field(default="", description="Email address to send alerts to. Empty string uses system default.")


class MattermostServiceModel(BaseModel):
    type: Literal["Mattermost"] = Field(description="Alert service type identifier for Mattermost.")
    url: Secret[HttpUrl] = Field(description="Mattermost webhook URL for posting alerts.")
    username: NonEmptyString = Field(description="Username to display when posting alerts to Mattermost.")
    channel: str = Field(
        default="",
        description="Mattermost channel name to post alerts to. Empty string uses webhook default.",
    )
    icon_url: Literal[""] | HttpUrl = Field(
        default="",
        description="URL of icon image to display with alert messages. Empty string uses default.",
    )


class OpsGenieServiceModel(BaseModel):
    type: Literal["OpsGenie"] = Field(description="Alert service type identifier for OpsGenie.")
    api_key: Secret[NonEmptyString] = Field(description="OpsGenie API key for authentication.")
    api_url: Literal[""] | HttpUrl = Field(
        default="",
        description="OpsGenie API URL. Empty string uses default OpsGenie endpoint.",
    )


class PagerDutyServiceModel(BaseModel):
    type: Literal["PagerDuty"] = Field(description="Alert service type identifier for PagerDuty.")
    service_key: Secret[NonEmptyString] = Field(description="PagerDuty service integration key for sending alerts.")
    client_name: NonEmptyString = Field(description="Client name to identify the source of alerts in PagerDuty.")


class SlackServiceModel(BaseModel):
    type: Literal["Slack"] = Field(description="Alert service type identifier for Slack.")
    url: Secret[HttpUrl] = Field(description="Slack webhook URL for posting alert messages.")


class SNMPTrapServiceModel(BaseModel):
    type: Literal["SNMPTrap"] = Field(description="Alert service type identifier for SNMP traps.")
    host: str = Field(description="SNMP trap receiver hostname or IP address.")
    port: TcpPort = Field(description="TCP port number for SNMP trap receiver.")
    v3: bool = Field(description="Whether to use SNMP v3 instead of v1/v2c.")
    # v1/v2
    community: NonEmptyString | None = Field(
        default=None,
        description="SNMP community string for v1/v2c authentication or `null` for v3.",
    )
    # v3
    v3_username: NonEmptyString | None = Field(
        default=None,
        description="SNMP v3 username for authentication or `null` for v1/v2c.",
    )
    v3_authkey: Secret[NonEmptyString | None] = Field(
        default=None,
        description="SNMP v3 authentication key or `null` if not using authentication.",
    )
    v3_privkey: Secret[NonEmptyString | None] = Field(
        default=None,
        description="SNMP v3 privacy key for encryption or `null` if not using privacy.",
    )
    v3_authprotocol: Literal[None, "MD5", "SHA", "128SHA224", "192SHA256", "256SHA384", "384SHA512"] = Field(
        default=None,
        description="SNMP v3 authentication protocol or `null` for no authentication.",
    )
    v3_privprotocol: Literal[None, "DES", "3DESEDE", "AESCFB128", "AESCFB192", "AESCFB256", "AESBLUMENTHALCFB192",
                             "AESBLUMENTHALCFB256"] = Field(
        default=None,
        description="SNMP v3 privacy protocol for encryption or `null` for no privacy.",
    )


class TelegramServiceModel(BaseModel):
    type: Literal["Telegram"] = Field(description="Alert service type identifier for Telegram.")
    bot_token: Secret[NonEmptyString] = Field(description="Telegram bot token for API authentication.")
    chat_ids: list[int] = Field(
        min_length=1,
        description="List of Telegram chat IDs to send alerts to (minimum 1 required).",
    )


class VictorOpsServiceModel(BaseModel):
    type: Literal["VictorOps"] = Field(description="Alert service type identifier for VictorOps (now Splunk On-Call).")
    api_key: Secret[NonEmptyString] = Field(description="VictorOps API key for authentication.")
    routing_key: NonEmptyString = Field(
        description="VictorOps routing key to determine alert destination and escalation policy.",
    )


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
