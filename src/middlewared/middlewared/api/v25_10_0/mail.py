from typing import Literal

from pydantic import Secret, Field

from middlewared.api.base import (
    BaseModel, EmailString, ForUpdateMetaclass, Excluded, excluded_field, NotRequired, LongString
)


__all__ = ["MailEntry", "MailUpdateArgs", "MailUpdateResult", "MailSendArgs", "MailSendResult"]


class MailEntryOAuth(BaseModel):
    provider: str
    client_id: str
    client_secret: str
    refresh_token: Secret[str]


class MailEntry(BaseModel):
    fromemail: EmailString
    """The sending address that the mail server will use for sending emails."""
    fromname: str
    outgoingserver: str
    """Hostname or IP address of the SMTP server used for sending emails."""
    port: int
    security: Literal["PLAIN", "SSL", "TLS"]
    """Type of encryption."""
    smtp: bool
    """Whether SMTP authentication is enabled and `user`, `pass` are required."""
    user: str | None
    pass_: Secret[str | None] = Field(alias="pass")
    oauth: Secret[MailEntryOAuth | None]
    id: int


class MailUpdateOAuth(MailEntryOAuth):
    provider: str = NotRequired
    refresh_token: Secret[LongString]


class MailUpdate(MailEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()
    oauth: Secret[MailUpdateOAuth | None]


class MailSendMessage(BaseModel):
    subject: str
    text: LongString = NotRequired
    """Formatted to HTML using Markdown and rendered using default email template."""
    html: LongString | None = NotRequired
    """Custom HTML (overrides `text`). If null, no HTML MIME part will be added to the email."""
    to: list[str] = NotRequired
    cc: list[str] = NotRequired
    interval: int | None = NotRequired
    channel: str | None = NotRequired
    timeout: int = 300
    attachments: bool = False
    """If set to true, a list compromised of the following dict is required via HTTP upload:
        - headers (array)
            - name (string)
            - value (string)
            - params (object)
        - content (string)

        ```[
         {
          "headers": [
           {
            "name": "Content-Transfer-Encoding",
            "value": "base64"
           },
           {
            "name": "Content-Type",
            "value": "application/octet-stream",
            "params": {
             "name": "test.txt"
            }
           }
          ],
          "content": "dGVzdAo="
         }
        ]```
    """
    queue: bool = True
    extra_headers: dict = NotRequired


class MailUpdateArgs(BaseModel):
    data: MailUpdate


class MailUpdateResult(BaseModel):
    result: MailEntry


class MailSendArgs(BaseModel):
    message: MailSendMessage
    config: MailUpdate


class MailSendResult(BaseModel):
    result: bool
    """Whether the message was sent successfully."""
