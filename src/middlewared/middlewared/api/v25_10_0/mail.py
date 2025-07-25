from typing import Literal

from pydantic import Secret, Field

from middlewared.api.base import (
    BaseModel, EmailString, EmptyDict, ForUpdateMetaclass, Excluded, excluded_field, NotRequired, LongString
)

__all__ = ["MailEntry", "MailUpdateArgs", "MailUpdateResult", "MailSendArgs", "MailSendResult",
           "MailLocalAdministratorEmailArgs", "MailLocalAdministratorEmailResult"]


class MailEntryOAuth(BaseModel):
    provider: str
    """An email provider, e.g. "gmail", "outlook"."""
    client_id: str
    """OAuth client ID provided by the email provider."""
    client_secret: str
    """OAuth client secret provided by the email provider."""
    refresh_token: LongString
    """OAuth refresh token used to obtain new access tokens for email authentication."""


class MailEntry(BaseModel):
    fromemail: EmailString
    """The sending address that the mail server will use for sending emails."""
    fromname: str
    """Display name that will appear as the sender name in outgoing emails."""
    outgoingserver: str
    """Hostname or IP address of the SMTP server used for sending emails."""
    port: int
    """TCP port number for the SMTP server connection."""
    security: Literal["PLAIN", "SSL", "TLS"]
    """Type of encryption."""
    smtp: bool
    """Whether SMTP authentication is enabled and `user`, `pass` are required."""
    user: str | None
    """SMTP username."""
    pass_: Secret[str | None] = Field(alias="pass")
    """SMTP password."""
    oauth: Secret[MailEntryOAuth | EmptyDict | None]
    id: int
    """Unique identifier for this mail configuration."""


class MailUpdate(MailEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class MailSendMessage(BaseModel):
    subject: str
    """Subject line for the email message."""
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

    * headers *(array)*
        * name *(string)*
        * value *(string)*
        * params *(object)*

    * content *(string)*

    Example:
    ```json
    [
      {
        \"headers\": [
          {
            \"name\": \"Content-Transfer-Encoding\",
            \"value\": \"base64\"
          },
          {
            \"name\": \"Content-Type\",
            \"value\": \"application/octet-stream\",
            \"params\": {
              \"name\": \"test.txt\"
            }
          }
        ],
        \"content\": \"dGVzdAo=\"
      }
    ]
    ```
    """
    queue: bool = True
    """Queue the message to be sent later if it fails to send."""
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
    config: MailUpdate = Field(default_factory=MailUpdate)


class MailSendResult(BaseModel):
    result: bool
    """The message was sent successfully."""


class MailLocalAdministratorEmailArgs(BaseModel):
    pass


class MailLocalAdministratorEmailResult(BaseModel):
    result: str | None
