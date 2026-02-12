from typing import Literal

from pydantic import Field, Secret

from middlewared.api.base import (
    BaseModel, ForUpdateMetaclass, NotRequired, single_argument_args, LongString, EmailString, single_argument_result
)


__all__ = [
    "SupportEntry", "SupportAttachTicketArgs", "SupportAttachTicketResult", "SupportAttachTicketMaxSizeArgs",
    "SupportAttachTicketMaxSizeResult", "SupportFieldsArgs", "SupportFieldsResult", "SupportIsAvailableArgs",
    "SupportIsAvailableResult", "SupportIsAvailableAndEnabledArgs", "SupportIsAvailableAndEnabledResult",
    "SupportNewTicketArgs", "SupportNewTicketResult", "SupportSimilarIssuesArgs", "SupportSimilarIssuesResult",
    "SupportUpdateArgs", "SupportUpdateResult",
]


class SupportEntry(BaseModel):
    id: int
    """Unique identifier for the support configuration."""
    enabled: bool | None
    """Whether support is enabled. `null` if not available."""
    name: str
    """Primary contact name for support."""
    title: str
    """Primary contact title or role."""
    email: str
    """Primary contact email address."""
    phone: str
    """Primary contact phone number."""
    secondary_name: str
    """Secondary contact name for support."""
    secondary_title: str
    """Secondary contact title or role."""
    secondary_email: str
    """Secondary contact email address."""
    secondary_phone: str
    """Secondary contact phone number."""


class SupportNewTicketCommunity(BaseModel):
    title: str = Field(max_length=200)
    """Title of the support ticket."""
    body: str = Field(max_length=20000)
    """Detailed description of the issue or request."""
    attach_debug: bool = False
    """Whether to attach debug information to the ticket."""
    token: Secret[str]
    """Authentication token for creating community tickets."""
    type: Literal['BUG', 'FEATURE']
    """Type of ticket being created."""
    cc: list[EmailString] = []
    """Array of email addresses to copy on the ticket."""


class SupportNewTicketEnterprise(BaseModel):
    title: str = Field(max_length=200)
    """Title of the support ticket."""
    body: str = Field(max_length=20000)
    """Detailed description of the issue or request."""
    category: str
    """Category or classification of the support issue."""
    attach_debug: bool = False
    """Whether to attach debug information to the ticket."""
    criticality: str
    """Priority or criticality level of the issue."""
    environment: LongString
    """Description of the environment where the issue occurs."""
    phone: str
    """Contact phone number for this ticket."""
    name: str
    """Contact name for this ticket."""
    email: EmailString
    """Contact email address for this ticket."""
    cc: list[EmailString] = []
    """Array of email addresses to copy on the ticket."""


class SupportSimilarIssue(BaseModel):
    url: str = NotRequired
    """URL link to the similar issue or knowledge base article."""
    summary: str = NotRequired
    """Brief summary of the similar issue."""

    class Config:
        extra = 'allow'


class SupportUpdate(SupportEntry, metaclass=ForUpdateMetaclass):
    pass


@single_argument_args('data')
class SupportAttachTicketArgs(BaseModel):
    ticket: int
    """Ticket number to attach the file to."""
    filename: LongString
    """Path to the file to attach to the ticket."""
    token: Secret[str] = NotRequired
    """Authentication token for attaching files."""


class SupportAttachTicketResult(BaseModel):
    result: None
    """Returns `null` on successful file attachment."""


class SupportAttachTicketMaxSizeArgs(BaseModel):
    pass


class SupportAttachTicketMaxSizeResult(BaseModel):
    result: int
    """Maximum file size in bytes allowed for ticket attachments."""


class SupportFieldsArgs(BaseModel):
    pass


class SupportFieldsResult(BaseModel):
    result: list[list[str]]
    """Pairs of field names and their titles for Proactive Support."""


class SupportIsAvailableArgs(BaseModel):
    pass


class SupportIsAvailableResult(BaseModel):
    result: bool
    """Whether support functionality is available on this system."""


class SupportIsAvailableAndEnabledArgs(BaseModel):
    pass


class SupportIsAvailableAndEnabledResult(BaseModel):
    result: bool
    """Whether support functionality is both available and enabled."""


class SupportNewTicketArgs(BaseModel):
    data: SupportNewTicketEnterprise | SupportNewTicketCommunity
    """Support ticket data for either enterprise or community support."""


@single_argument_result
class SupportNewTicketResult(BaseModel):
    ticket: int | None
    """Ticket number if successfully created. `null` if creation failed."""
    url: str | None
    """URL to view the created ticket. `null` if not available."""
    has_debug: bool
    """Whether debug information was attached to the ticket."""


class SupportSimilarIssuesArgs(BaseModel):
    query: str
    """Search query to find similar issues or knowledge base articles."""


class SupportSimilarIssuesResult(BaseModel):
    result: list[SupportSimilarIssue]
    """Array of similar issues found based on the search query."""


class SupportUpdateArgs(BaseModel):
    data: SupportUpdate
    """Updated support configuration data."""


class SupportUpdateResult(BaseModel):
    result: SupportEntry
    """The updated support configuration."""
