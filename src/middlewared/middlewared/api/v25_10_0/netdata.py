from pydantic import Field

from middlewared.api.base import BaseModel, NonEmptyString


class ChartMetricsDataArgs(BaseModel):
    before: int = 0
    after: int = -1


class ChartMetricsArgs(BaseModel):
    chart: NonEmptyString
    data: ChartMetricsDataArgs = Field(default_factory=lambda: ChartMetricsDataArgs())


class ChartMetricsResult(BaseModel):
    result: dict


class ChartDetailsArgs(BaseModel):
    chart: NonEmptyString


class ChartDetailsResult(BaseModel):
    result: dict
