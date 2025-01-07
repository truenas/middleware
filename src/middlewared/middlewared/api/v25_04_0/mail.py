from typing import Literal

from pydantic import Field, Secret, SecretStr

from middlewared.api.base import BaseModel, EmailString, ForUpdateMetaclass, Excluded, excluded_field, LongString


__all__ = [
    "MailEntry", "MailUpdateArgs", "MailUpdateResult", "MailSendArgs",
    "MailSendResult", "MailSendRawArgs", "MailSendRawResult"
]


class MailOAuth(BaseModel):
    provider: str
    client_id: str
    client_secret: str
    refresh_token: SecretStr


class MailEntry(BaseModel):
    fromemail: EmailString
    """A sending address which the mail server will use for sending emails."""
    fromname: str
    outgoingserver: str
    """The hostname or IP address of SMTP server used for sending an email."""
    port: int
    security: Literal["PLAIN", "SSL", "TLS"]
    """Type of encryption desired."""
    smtp: bool
    """Whether SMTP authentication is enabled and `user`/`pass` are required attributes."""
    user: str | None
    pass_: SecretStr | None = Field(alias="pass")
    oauth: Secret[MailOAuth | None]
    id: int


class MailUpdate(MailEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class MailSendMessage(BaseModel):
    subject: str
    text: LongString = ""
    html: LongString | None = None
    to: list[str] = []
    cc: list[str] = []
    interval: int | None = None
    channel: str | None = None
    timeout: int = 300
    attachments: bool = False
    queue: bool = True
    extra_headers: dict = {}


class MailUpdateArgs(BaseModel):
    data: MailUpdate


class MailUpdateResult(BaseModel):
    result: MailEntry


class MailSendArgs(BaseModel):
    message: MailSendMessage
    config: MailUpdate = MailUpdate()


class MailSendResult(BaseModel):
    result: bool
    """Whether the message sent successfully."""


class MailSendRawArgs(BaseModel):
    message: MailSendMessage
    config: MailUpdate = MailUpdate()


class MailSendRawResult(BaseModel):
    result: bool
    """Whether the message sent successfully."""
