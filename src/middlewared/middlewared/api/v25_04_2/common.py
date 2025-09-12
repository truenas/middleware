from typing import Annotated, Self

from pydantic import AfterValidator, Field, model_validator

from middlewared.api.base import BaseModel
from middlewared.utils import validate_filters, validate_options
from middlewared.utils.cron import croniter_for_schedule

__all__ = ["QueryFilters", "QueryOptions", "QueryArgs", "GenericQueryResult"]

QueryFilters = Annotated[list, AfterValidator(validate_filters)]


class QueryOptions(BaseModel):
    relationships: bool = True
    extend: str | None = None
    extend_context: str | None = None
    prefix: str | None = None
    extra: dict = {}
    """ Extra options are defined on a per-endpoint basis and are described in the documentation for the associated
    query method. """
    order_by: list[str] = Field(default=[], examples=[['size', '-devname', 'nulls_first:-expiretime']])
    """ An array of field names describing the manner in which query results should be ordered. The field names may
    also have one of more of the following special prefixes: `-` (reverse sort direction), `nulls_first:` (place
    any null values at the head of the results list), `nulls_last:` (place any null values at the tail of the
    results list). """
    select: list[str | list] = Field(default=[], examples=[['username', 'Authentication.status']])
    """ An array of field names specifying the exact fields to include in the query return. The dot character `.`
    may be used to explicitly select only subkeys of the query result. """
    count: bool = False
    """ Return a numeric value representing the number of items that match the specified `query-filters`. """
    get: bool = False
    """ Return the JSON object of the first result matching the specified `query-filters`. The query fails
    if there specified `query-filters` return no results. """
    offset: int = 0
    """ This specifies the beginning offset of the results array. When combined with the `limit` query-option
    it may be used to implement pagination of large results arrays. WARNING: some query methods provide
    volatile results and the onus is on the developer to understand whether pagination is appropriate
    for a particular query API method. """
    limit: int = 0
    """ This specifies the maximum number of results matching the specified `query-filters` to return. When
    combined wtih the `offset` query-option it may be used to implement pagination of large results arrays.
    WARNING: some query methods provide volatile results and the onus is on the developer to understand whether
    pagination is appropriate for a particular query API method. """
    force_sql_filters: bool = False

    @model_validator(mode='after')
    def validate_query_options(self) -> Self:
        validate_options(self.model_dump())
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
