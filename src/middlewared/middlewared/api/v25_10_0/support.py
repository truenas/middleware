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
    enabled: bool | None
    name: str
    title: str
    email: str
    phone: str
    secondary_name: str
    secondary_title: str
    secondary_email: str
    secondary_phone: str


class SupportSimilarIssue(BaseModel):
    url: str = NotRequired
    summary: str = NotRequired

    class Config:
        extra = 'allow'


class SupportUpdate(SupportEntry, metaclass=ForUpdateMetaclass):
    pass


@single_argument_args('data')
class SupportAttachTicketArgs(BaseModel):
    ticket: int
    filename: LongString
    token: Secret[str] = NotRequired


class SupportAttachTicketResult(BaseModel):
    result: None


class SupportAttachTicketMaxSizeArgs(BaseModel):
    pass


class SupportAttachTicketMaxSizeResult(BaseModel):
    result: int


class SupportFieldsArgs(BaseModel):
    pass


class SupportFieldsResult(BaseModel):
    result: list[list[str]]
    """Pairs of field names and their titles for Proactive Support."""


class SupportIsAvailableArgs(BaseModel):
    pass


class SupportIsAvailableResult(BaseModel):
    result: bool


class SupportIsAvailableAndEnabledArgs(BaseModel):
    pass


class SupportIsAvailableAndEnabledResult(BaseModel):
    result: bool


@single_argument_args('data')
class SupportNewTicketArgs(BaseModel):
    title: str = Field(max_length=200)
    body: str = Field(max_length=20000)
    category: str = NotRequired
    attach_debug: bool = False
    token: Secret[str] = NotRequired
    type: Literal['BUG', 'FEATURE'] = NotRequired
    criticality: str = NotRequired
    environment: LongString = NotRequired
    phone: str = NotRequired
    name: str = NotRequired
    email: EmailString = NotRequired
    cc: list[EmailString] = []


@single_argument_result
class SupportNewTicketResult(BaseModel):
    ticket: int | None
    url: str | None
    has_debug: bool


class SupportSimilarIssuesArgs(BaseModel):
    query: str


class SupportSimilarIssuesResult(BaseModel):
    result: list[SupportSimilarIssue]


class SupportUpdateArgs(BaseModel):
    data: SupportUpdate


class SupportUpdateResult(BaseModel):
    result: SupportEntry
