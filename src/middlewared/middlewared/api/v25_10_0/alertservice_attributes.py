from typing import Annotated, Literal, Union

from pydantic import Discriminator, Field, Secret

from middlewared.api.base import BaseModel, HttpUrl, NonEmptyString, TcpPort

__all__ = ["AlertServiceAttributes"]


class AWSSNSServiceModel(BaseModel):
    type: Literal["AWSSNS"]
    region: NonEmptyString
    topic_arn: NonEmptyString
    aws_access_key_id: NonEmptyString
    aws_secret_access_key: Secret[NonEmptyString]


class InfluxDBServiceModel(BaseModel):
    type: Literal["InfluxDB"]
    host: NonEmptyString
    username: NonEmptyString
    password: Secret[NonEmptyString]
    database: NonEmptyString
    series_name: NonEmptyString


class MailServiceModel(BaseModel):
    type: Literal["Mail"]
    email: str = ""


class MattermostServiceModel(BaseModel):
    type: Literal["Mattermost"]
    url: Secret[HttpUrl]
    username: NonEmptyString
    channel: str = ""
    icon_url: HttpUrl = ""


class OpsGenieServiceModel(BaseModel):
    type: Literal["OpsGenie"]
    api_key: Secret[NonEmptyString]
    api_url: HttpUrl = ""


class PagerDutyServiceModel(BaseModel):
    type: Literal["PagerDuty"]
    service_key: Secret[NonEmptyString]
    client_name: NonEmptyString


class SlackServiceModel(BaseModel):
    type: Literal["Slack"]
    url: Secret[HttpUrl]


class SNMPTrapServiceModel(BaseModel):
    type: Literal["SNMPTrap"]
    host: str
    port: TcpPort
    v3: bool
    # v1/v2
    community: NonEmptyString | None = None
    # v3
    v3_username: NonEmptyString | None = None
    v3_authkey: Secret[NonEmptyString | None] = None
    v3_privkey: Secret[NonEmptyString | None] = None
    v3_authprotocol: Literal[None, "MD5", "SHA", "128SHA224", "192SHA256", "256SHA384", "384SHA512"] = None
    v3_privprotocol: Literal[None, "DES", "3DESEDE", "AESCFB128", "AESCFB192", "AESCFB256", "AESBLUMENTHALCFB192",
                             "AESBLUMENTHALCFB256"] = None


class TelegramServiceModel(BaseModel):
    type: Literal["Telegram"]
    bot_token: Secret[NonEmptyString]
    chat_ids: list[int] = Field(min_length=1)


class VictorOpsServiceModel(BaseModel):
    type: Literal["VictorOps"]
    api_key: Secret[NonEmptyString]
    routing_key: NonEmptyString


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
