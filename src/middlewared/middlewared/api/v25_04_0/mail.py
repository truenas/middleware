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
    fromemail: EmailString = ""
    """The sending address for the mail server to use for sending emails."""
    fromname: str = ""
    outgoingserver: str = ""
    """The hostname or IP address of the SMTP server to use for sending emails."""
    port: int
    security: Literal["PLAIN", "SSL", "TLS"] = "PLAIN"
    """Type of encryption desired."""
    smtp: bool = False
    """Whether SMTP authentication is enabled and `user`/`pass` are required attributes."""
    user: str | None = None
    pass_: SecretStr | None = Field(alias="pass", default=None)
    oauth: Secret[MailOAuth | None] = None
    id: int


class MailUpdate(MailEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class MailSendMessage(BaseModel):
    subject: str
    text: LongString = ""
    """Will be formatted to HTML using Markdown and rendered using default E-Mail template."""
    html: LongString | None = None
    """Custom HTML to use instead of `text`. If null, no HTML MIME part will be added to E-Mail."""
    to: list[str] = []
    cc: list[str] = []
    interval: int | None = None
    channel: str | None = None
    timeout: int = 300
    attachments: bool = False
    """
    If set, an array compromised of the following object schema is required via HTTP upload:

    - headers (array)
      - name (string)
      - value (string)
      - params (object)
    - content (string)

    Example:
    [
      {
        "headers": [
          {
            "name": "Content-Transfer-Encoding",
            "value": "base64"
          },
          {
            "name": "Content-Type",
            "value": "application/octet-stream",
            "params": {"name": "test.txt"}
          }
        ],
        "content": "dGVzdAo="
      }
    ]
    """
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
