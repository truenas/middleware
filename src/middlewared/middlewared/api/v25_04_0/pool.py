from typing import Annotated

from pydantic import Field

from middlewared.api.base import BaseModel, NonEmptyString, single_argument_args


@single_argument_args('options')
class DDTPruneArgs(BaseModel):
    pool_name: NonEmptyString
    percentage: Annotated[int | None, Field(ge=1, le=100, default=None)]
    days: Annotated[int | None, Field(ge=1, default=None)]


class DDTPruneResult(BaseModel):
    result: None


class DDTPrefetchArgs(BaseModel):
    pool_name: NonEmptyString


class DDTPrefetchResult(BaseModel):
    result: None
