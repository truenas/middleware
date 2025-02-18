from typing import Literal

from pydantic import Secret, Field

from middlewared.api.base import (
    BaseModel, EmailString, ForUpdateMetaclass, Excluded, excluded_field, NotRequired, LongString
)


__all__ = ["MailEntry", "MailUpdateArgs", "MailUpdateResult", "MailSendArgs", "MailSendResult"]


class MailEntryOAuth(BaseModel):
    provider: str = NotRequired
    """An email provider, e.g. "gmail", "outlook"."""
    client_id: str = NotRequired
    client_secret: str = NotRequired
    refresh_token: Secret[LongString] = NotRequired


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
    """SMTP username."""
    pass_: Secret[str | None] = Field(alias="pass")
    """SMTP password."""
    oauth: Secret[MailEntryOAuth | None]
    id: int


class MailUpdateOAuth(MailEntryOAuth):
    client_id: str
    client_secret: str
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
    """Email recipients. Defaults to all local administrators."""
    cc: list[str] = NotRequired
    """Email CC recipients, if any."""
    interval: int | None = NotRequired
    """In seconds."""
    channel: str | None = NotRequired
    """Defaults to "truenas"."""
    timeout: int = 300
    """Time limit for connecting to the SMTP server in seconds."""
    attachments: bool = False
    """If set to true, an array compromised of the following object is required via HTTP upload:
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
    """Whether to queue the message to be sent later if it fails to send."""
    extra_headers: dict = NotRequired
    """Any additional headers to include in the email message."""


class MailUpdateArgs(BaseModel):
    data: MailUpdate
    """Mail configuration fields to update."""


class MailUpdateResult(BaseModel):
    result: MailEntry
    """The resulting mail configuration."""


class MailSendArgs(BaseModel):
    message: MailSendMessage
    config: MailUpdate


class MailSendResult(BaseModel):
    result: bool
    """Whether the message was sent successfully."""
