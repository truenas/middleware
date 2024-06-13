from typing import Any, List, Optional

from middlewared.api.base import *

__all__ = ["QueryOptions", "QueryArgs"]


class QueryOptions(BaseModel):
    relationships: bool = True
    extend: Optional[str] = None
    extend_context: Optional[str] = None
    prefix: Optional[str] = None
    extra: dict = {}
    order_by: List[str] = []
    select: List[str] = []
    count: bool = False
    get: bool = False
    offset: int = 0
    limit: int = 0
    force_sql_filters: bool = False


class QueryArgs(BaseModel):
    filters: List[Any] = []  # FIXME: Add validation here
    options: QueryOptions = QueryOptions()
