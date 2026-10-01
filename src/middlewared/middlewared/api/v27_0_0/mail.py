from typing import Literal

from pydantic import Field, Secret

from middlewared.api.base import (
    BaseModel,
    EmailString,
    EmptyDict,
    Excluded,
    ForUpdateMetaclass,
    LongString,
    NotRequired,
    excluded_field,
)

__all__ = ["MailEntry", "MailUpdateArgs", "MailUpdateResult", "MailSendArgs", "MailSendResult",
           "MailLocalAdministratorEmailArgs", "MailLocalAdministratorEmailResult"]


class MailEntryOAuth(BaseModel):
    provider: str = Field(description="An email provider, e.g. \"gmail\", \"outlook\".")
    client_id: str = Field(description="OAuth client ID provided by the email provider.")
    client_secret: str = Field(description="OAuth client secret provided by the email provider.")
    refresh_token: LongString = Field(
        description="OAuth refresh token used to obtain new access tokens for email authentication.",
    )


class MailEntry(BaseModel):
    fromemail: EmailString = Field(description="The sending address that the mail server will use for sending emails.")
    fromname: str = Field(description="Display name that will appear as the sender name in outgoing emails.")
    outgoingserver: str = Field(description="Hostname or IP address of the SMTP server used for sending emails.")
    port: int = Field(description="TCP port number for the SMTP server connection.")
    security: Literal["PLAIN", "SSL", "TLS"] = Field(description="Type of encryption.")
    smtp: bool = Field(description="Whether SMTP authentication is enabled and `user`, `pass` are required.")
    user: str | None = Field(description="SMTP username.")
    pass_: Secret[str | None] = Field(alias="pass", description="SMTP password.")
    oauth: Secret[MailEntryOAuth | EmptyDict | None] = Field(
        description="OAuth configuration for email providers that support it or `null` for basic authentication.",
    )
    id: int = Field(description="Unique identifier for this mail configuration.")


class MailUpdate(MailEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class MailSendMessage(BaseModel):
    subject: str = Field(description="Subject line for the email message.")
    text: LongString = Field(
        default=NotRequired,
        description="Formatted to HTML using Markdown and rendered using default email template.",
    )
    html: LongString | None = Field(
        default=NotRequired,
        description="Custom HTML (overrides `text`). If null, no HTML MIME part will be added to the email.",
    )
    to: list[str] = Field(default=NotRequired, description="Email recipients. Defaults to all local administrators.")
    cc: list[str] = Field(default=NotRequired, description="Email CC recipients, if any.")
    interval: int | None = Field(default=NotRequired, description="In seconds.")
    channel: str | None = Field(default=NotRequired, description="Defaults to \"truenas\".")
    timeout: int = Field(default=300, description="Time limit for connecting to the SMTP server in seconds.")
    attachments: bool = Field(
        default=False,
        description=(
            "If set to true, an array compromised of the following object is required via HTTP upload:\n"
            "\n"
            "* headers *(array)*\n"
            "    * name *(string)*\n"
            "    * value *(string)*\n"
            "    * params *(object)*\n"
            "\n"
            "* content *(string)*\n"
            "\n"
            "Example:\n"
            "[\n"
            "  {\n"
            "    \"headers\": [\n"
            "      {\n"
            "        \"name\": \"Content-Transfer-Encoding\",\n"
            "        \"value\": \"base64\"\n"
            "      },\n"
            "      {\n"
            "        \"name\": \"Content-Type\",\n"
            "        \"value\": \"application/octet-stream\",\n"
            "        \"params\": {\n"
            "          \"name\": \"test.txt\"\n"
            "        }\n"
            "      }\n"
            "    ],\n"
            "    \"content\": \"dGVzdAo=\"\n"
            "  }\n"
            "]"
        ),
    )
    queue: bool = Field(default=True, description="Queue the message to be sent later if it fails to send.")
    extra_headers: dict = Field(
        default=NotRequired,
        description="Any additional headers to include in the email message.",
    )


class MailUpdateArgs(BaseModel):
    data: MailUpdate = Field(description="Mail configuration fields to update.")


class MailUpdateResult(BaseModel):
    result: MailEntry = Field(description="The resulting mail configuration.")


class MailSendArgs(BaseModel):
    message: MailSendMessage = Field(description="Email message content and configuration.")
    config: MailUpdate = Field(
        default_factory=MailUpdate,
        description="Optional mail configuration overrides for this message.",
    )


class MailSendResult(BaseModel):
    result: None = Field(description="The message was sent successfully.")

    @classmethod
    def to_previous(cls, value):
        return {"result": True}


class MailLocalAdministratorEmailArgs(BaseModel):
    pass


class MailLocalAdministratorEmailResult(BaseModel):
    result: str | None = Field(description="Email address of the local administrator or `null` if not configured.")
