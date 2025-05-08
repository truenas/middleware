from typing import Annotated, Self

from middlewared.api.base import BaseModel
from middlewared.utils import filters
from middlewared.utils.cron import croniter_for_schedule

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


class CronModel(BaseModel):
    """
    Each field can either be a single value or a comma-separated list of values.
    A \"*\" represents the full list of values.
    """
    minute: str = "*"
    """\"00\" - \"59\""""
    hour: str = "*"
    """\"00\" - \"23\""""
    dom: str = "*"
    """\"1\" - \"31\""""
    month: str = "*"
    """\"1\" (January) - \"12\" (December)"""
    dow: str = "*"
    """\"1\" (Monday) - \"7\" (Sunday)"""

    @model_validator(mode="after")
    def validate_attrs(self):
        try:
            croniter_for_schedule(self.model_dump())
        except Exception as e:
            raise ValueError(f"Please ensure fields match cron syntax - {e}")

        return self
