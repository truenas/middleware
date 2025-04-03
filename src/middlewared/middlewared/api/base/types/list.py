from typing import Annotated, TypeVar

from pydantic_core import PydanticCustomError
from pydantic import AfterValidator, Field

__all__ = ['UniqueList']


T = TypeVar('T')


def _validate_unique_list(v: list[T]) -> list[T]:
    """Raise `PydanticCustomError` if any item in `v` is equal to any other item in `v`."""
    # Use equals comparison instead of `set` to support unhashable types like `BaseModel`.
    for i in range(len(v)):
        for j in range(i + 1, len(v)):
            if v[i] == v[j]:
                raise PydanticCustomError('unique_list', 'List must be unique')
    return v


UniqueList = Annotated[list[T], AfterValidator(_validate_unique_list), Field(json_schema_extra={'uniqueItems': True})]
