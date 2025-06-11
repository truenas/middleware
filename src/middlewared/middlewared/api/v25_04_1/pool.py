from typing import Annotated

from pydantic import Field

from middlewared.api.base import BaseModel, NonEmptyString, single_argument_args


@single_argument_args('options')
class PoolDdtPruneArgs(BaseModel):
    pool_name: NonEmptyString
    percentage: Annotated[int | None, Field(ge=1, le=100, default=None)]
    days: Annotated[int | None, Field(ge=1, default=None)]


class PoolDdtPruneResult(BaseModel):
    result: None


class PoolDdtPrefetchArgs(BaseModel):
    pool_name: NonEmptyString


class PoolDdtPrefetchResult(BaseModel):
    result: None
