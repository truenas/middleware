from typing import Any
from typing_extensions import Annotated, Self

from middlewared.api.base import BaseModel
from middlewared.validators import QueryFilters as QueryFiltersValidator
from middlewared.validators import QueryOptions as QueryOptionsValidator

from pydantic import AfterValidator, model_validator

__all__ = ["QueryFilters", "QueryOptions", "QueryArgs"]

qf_validator = QueryFiltersValidator()
qo_validator = QueryOptionsValidator()

QueryFilters = Annotated[list, AfterValidator(qf_validator)]


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
        qo_validator(self.dict())
        return self


class QueryArgs(BaseModel):
    filters: QueryFilters = []
    options: QueryOptions = QueryOptions()
