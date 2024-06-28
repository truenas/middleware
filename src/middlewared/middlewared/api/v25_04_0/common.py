from typing import Any

from middlewared.api.base import BaseModel

__all__ = ["QueryOptions", "QueryArgs"]


class QueryOptions(BaseModel):
    relationships: bool = True
    extend: str | None = None
    extend_context: str | None = None
    prefix: str | None = None
    extra: dict = {}
    order_by: list[str] = []
    select: list[str] = []
    count: bool = False
    get: bool = False
    offset: int = 0
    limit: int = 0
    force_sql_filters: bool = False


class QueryArgs(BaseModel):
    filters: list[Any] = []  # FIXME: Add validation here
    options: QueryOptions = QueryOptions()
