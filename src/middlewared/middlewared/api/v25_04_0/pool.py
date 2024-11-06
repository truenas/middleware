from pydantic import conint, Field

from middlewared.api.base import BaseModel, NonEmptyString, single_argument_args


@single_argument_args('options')
class DDTPruneArgs(BaseModel):
    pool_name: NonEmptyString
    percentage: conint(ge=1, le=100) | None = Field(default=None)
    days: conint(ge=1) | None = Field(default=None)


class DDTPruneResult(BaseModel):
    result: None


class DDTPrefetchArgs(BaseModel):
    pool_name: NonEmptyString


class DDTPrefetchResult(BaseModel):
    result: None
