from typing_extensions import Annotated, Self

from middlewared.api.base import BaseModel
from middlewared.utils import filters

from pydantic import AfterValidator, model_validator

__all__ = ["QueryFilters", "QueryOptions", "QueryArgs", "GenericQueryResult"]

filter_obj = filters()


def validate_query_filters(qf: list) -> list:
    filter_obj.validate_filters(qf)
    return qf


QueryFilters = Annotated[list, AfterValidator(validate_query_filters)]


class QueryOptions(BaseModel):
    relationships: bool = True
    extend: str | None = None
    extend_context: str | None = None
    prefix: str | None = None
    extra: dict = {}
    order_by: list[str] = []
    select: list[str | list] = []
    count: bool = False
    get: bool = False
    offset: int = 0
    limit: int = 0
    force_sql_filters: bool = False

    @model_validator(mode='after')
    def validate_query_options(self) -> Self:
        filter_obj.validate_options(self.dict())
        return self


class QueryArgs(BaseModel):
    filters: QueryFilters = []
    options: QueryOptions = QueryOptions()


class GenericQueryResult(BaseModel):
    result: list[dict] | dict | int
