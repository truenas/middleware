from datetime import datetime, time
from typing import Annotated, Literal, Self

from pydantic import AfterValidator, model_validator, Field

from middlewared.api.base import (
    BaseModel, JsonSchemaExtra, TimeString, croniter_for_schedule, validate_filters, validate_options
)

__all__ = ["QueryFilters", "QueryOptions", "QueryArgs", "GenericQueryResult", "CronModel", "TimeCronModel",
           "StorageTier"]

StorageTier = Literal['REGULAR', 'PERFORMANCE']
"""Storage performance tier. `REGULAR` uses standard-capacity drives; `PERFORMANCE` uses fast media (e.g. NVMe)."""

QF_DOC = 'List of filters for query results. See API documentation for "Query Methods" for more guidance.'
QueryFilters = Annotated[
    list,
    JsonSchemaExtra(description=QF_DOC, examples=[
        [["name", "=", "bob"]],
        [["OR", [["name", "=", "bob"], ["name", "=", "larry"]]]],
    ]),
    AfterValidator(validate_filters),
]


class QueryOptions(BaseModel):
    """ Query options customize the results returned by a query method. More complete documentation with examples \
    are covered in the "Query methods" section of the TrueNAS API documentation. """
    extra: dict = Field(
        default={},
        description=(
            "Extra options are defined on a per-endpoint basis and are described in the documentation for the "
            "associated query method."
        ),
    )
    order_by: list[str] = Field(
        default=[],
        examples=[['size', '-devname', 'nulls_first:-expiretime']],
        description=(
            "An array of field names describing the manner in which query results should be ordered. The field names "
            "may also have one of more of the following special prefixes: `-` (reverse sort direction), `nulls_first:` "
            "(place any null values at the head of the results list), `nulls_last:` (place any null values at the tail "
            "of the results list)."
        ),
    )
    select: list[str | list] = Field(
        default=[],
        examples=[['username', 'Authentication.status']],
        description=(
            "An array of field names specifying the exact fields to include in the query return. The dot character `.` "
            "may be used to explicitly select only subkeys of the query result."
        ),
    )
    count: bool = Field(
        default=False,
        description="Return a numeric value representing the number of items that match the specified `query-filters`.",
    )
    get: bool = Field(
        default=False,
        description=(
            "Return the JSON object of the first result matching the specified `query-filters`. The query fails if "
            "there specified `query-filters` return no results."
        ),
    )
    offset: int = Field(
        default=0,
        description=(
            "This specifies the beginning offset of the results array. When combined with the `limit` query-option it "
            "may be used to implement pagination of large results arrays. WARNING: some query methods provide volatile "
            "results and the onus is on the developer to understand whether pagination is appropriate for a particular "
            "query API method."
        ),
    )
    limit: int = Field(
        default=0,
        description=(
            "This specifies the maximum number of results matching the specified `query-filters` to return. When "
            "combined wtih the `offset` query-option it may be used to implement pagination of large results arrays.\n"
            "\n"
            "WARNING: Some query methods provide volatile results and the onus is on the developer to understand "
            "whether pagination is appropriate for a particular query API method."
        ),
    )
    force_sql_filters: bool = Field(
        default=False,
        description="Force use of SQL for result filtering to reduce response time. May not work for all methods.",
    )

    @model_validator(mode='after')
    def validate_query_options(self) -> Self:
        validate_options(self.model_dump())
        return self


class QueryArgs(BaseModel):
    filters: QueryFilters = Field(
        default=[],
        description=QF_DOC,
    )
    options: QueryOptions = Field(
        default=QueryOptions(),
        description="Query options including pagination, ordering, and additional parameters.",
    )


class GenericQueryResult(BaseModel):
    result: list[dict] | dict | int


class CronModel(BaseModel):
    """
    Each field can either be a single value or a comma-separated list of values.
    A "*" represents the full list of values.
    """
    minute: str = Field(default="*", description="\"00\" - \"59\".")
    hour: str = Field(default="*", description="\"00\" - \"23\".")
    dom: str = Field(default="*", description="\"1\" - \"31\".")
    month: str = Field(default="*", description="\"1\" (January) - \"12\" (December).")
    dow: str = Field(default="*", description="\"1\" (Monday) - \"7\" (Sunday).")

    @model_validator(mode="after")
    def validate_attrs(self):
        try:
            croniter_for_schedule(self.model_dump())
        except Exception as e:
            raise ValueError(f"Please ensure fields match cron syntax - {e}")

        return self


class TimeCronModel(CronModel):
    begin: TimeString = Field(default="00:00", description="Start time for the time window in HH:MM format.")
    end: TimeString = Field(default="23:59", description="End time for the time window in HH:MM format.")

    @model_validator(mode="after")
    def validate_time(self):
        begin = time(*map(int, self.begin.split(":")))
        end = time(*map(int, self.end.split(":")))

        assert begin <= end, "Begin time should be less than or equal to end time"

        iter_ = croniter_for_schedule(self.model_dump())
        for i in range(24 * 60):
            d = iter_.get_next(datetime)
            if begin <= d.time() <= end:
                break
        else:
            assert False, "Specified schedule does not match specified time interval"

        return self
