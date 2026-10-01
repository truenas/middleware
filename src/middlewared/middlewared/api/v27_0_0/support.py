from typing import Literal

from pydantic import Field, Secret

from middlewared.api.base import (
    BaseModel,
    EmailString,
    ForUpdateMetaclass,
    LongString,
    NotRequired,
    single_argument_args,
)

__all__ = [
    "SupportEntry", "SupportAttachTicketArgs", "SupportAttachTicketResult", "SupportAttachTicketMaxSizeArgs",
    "SupportAttachTicketMaxSizeResult", "SupportFieldsArgs", "SupportFieldsResult", "SupportIsAvailableArgs",
    "SupportIsAvailableResult", "SupportIsAvailableAndEnabledArgs", "SupportIsAvailableAndEnabledResult",
    "SupportNewTicketArgs", "SupportNewTicketResult", "SupportSimilarIssuesArgs", "SupportSimilarIssuesResult",
    "SupportUpdateArgs", "SupportUpdateResult", "SupportNewTicket"
]


class SupportEntry(BaseModel):
    id: int = Field(description="Unique identifier for the support configuration.")
    enabled: bool | None = Field(description="Whether support is enabled. `null` if not available.")
    name: str = Field(description="Primary contact name for support.")
    title: str = Field(description="Primary contact title or role.")
    email: str = Field(description="Primary contact email address.")
    phone: str = Field(description="Primary contact phone number.")
    secondary_name: str = Field(description="Secondary contact name for support.")
    secondary_title: str = Field(description="Secondary contact title or role.")
    secondary_email: str = Field(description="Secondary contact email address.")
    secondary_phone: str = Field(description="Secondary contact phone number.")


class SupportNewTicketCommunity(BaseModel):
    title: str = Field(max_length=200, description="Title of the support ticket.")
    body: str = Field(max_length=20000, description="Detailed description of the issue or request.")
    attach_debug: bool = Field(default=False, description="Whether to attach debug information to the ticket.")
    token: Secret[str] = Field(description="Authentication token for creating community tickets.")
    type: Literal['BUG', 'FEATURE'] = Field(description="Type of ticket being created.")
    cc: list[EmailString] = Field(default=[], description="Array of email addresses to copy on the ticket.")


class SupportNewTicketEnterprise(BaseModel):
    title: str = Field(max_length=200, description="Title of the support ticket.")
    body: str = Field(max_length=20000, description="Detailed description of the issue or request.")
    category: str = Field(description="Category or classification of the support issue.")
    attach_debug: bool = Field(default=False, description="Whether to attach debug information to the ticket.")
    criticality: str = Field(description="Priority or criticality level of the issue.")
    environment: LongString = Field(description="Description of the environment where the issue occurs.")
    phone: str = Field(description="Contact phone number for this ticket.")
    name: str = Field(description="Contact name for this ticket.")
    email: EmailString = Field(description="Contact email address for this ticket.")
    cc: list[EmailString] = Field(default=[], description="Array of email addresses to copy on the ticket.")


class SupportSimilarIssue(BaseModel):
    url: str = Field(default=NotRequired, description="URL link to the similar issue or knowledge base article.")
    summary: str = Field(default=NotRequired, description="Brief summary of the similar issue.")

    class Config:
        extra = 'allow'


class SupportUpdate(SupportEntry, metaclass=ForUpdateMetaclass):
    pass


@single_argument_args('data')
class SupportAttachTicketArgs(BaseModel):
    ticket: int = Field(description="Ticket number to attach the file to.")
    filename: LongString = Field(description="Path to the file to attach to the ticket.")
    token: Secret[str] = Field(default=NotRequired, description="Authentication token for attaching files.")


class SupportAttachTicketResult(BaseModel):
    result: None = Field(description="Returns `null` on successful file attachment.")


class SupportAttachTicketMaxSizeArgs(BaseModel):
    pass


class SupportAttachTicketMaxSizeResult(BaseModel):
    result: int = Field(description="Maximum file size in bytes allowed for ticket attachments.")


class SupportFieldsArgs(BaseModel):
    pass


class SupportFieldsResult(BaseModel):
    result: list[list[str]] = Field(description="Pairs of field names and their titles for Proactive Support.")


class SupportIsAvailableArgs(BaseModel):
    pass


class SupportIsAvailableResult(BaseModel):
    result: bool = Field(description="Whether support functionality is available on this system.")


class SupportIsAvailableAndEnabledArgs(BaseModel):
    pass


class SupportIsAvailableAndEnabledResult(BaseModel):
    result: bool = Field(description="Whether support functionality is both available and enabled.")


class SupportNewTicketArgs(BaseModel):
    data: SupportNewTicketEnterprise | SupportNewTicketCommunity = Field(
        description="Support ticket data for either enterprise or community support.",
    )


class SupportNewTicket(BaseModel):
    ticket: int | None = Field(description="Ticket number if successfully created. `null` if creation failed.")
    url: str | None = Field(description="URL to view the created ticket. `null` if not available.")
    has_debug: bool = Field(description="Whether debug information was attached to the ticket.")
    debug_attach_error: str | None = Field(
        description="If attaching debug information failed, the error message will appear here.",
    )


class SupportNewTicketResult(BaseModel):
    result: SupportNewTicket = Field(description="Created support ticket details.")


class SupportSimilarIssuesArgs(BaseModel):
    query: str = Field(description="Search query to find similar issues or knowledge base articles.")


class SupportSimilarIssuesResult(BaseModel):
    result: list[SupportSimilarIssue] = Field(description="Array of similar issues found based on the search query.")


class SupportUpdateArgs(BaseModel):
    data: SupportUpdate = Field(description="Updated support configuration data.")


class SupportUpdateResult(BaseModel):
    result: SupportEntry = Field(description="The updated support configuration.")
