from typing import Annotated, Hashable, List, TypeVar

from pydantic_core import PydanticCustomError

from pydantic import AfterValidator, Field

__all__ = ['UniqueList']

T = TypeVar('T', bound=Hashable)


def _validate_unique_list(v: list[T]) -> list[T]:
    if len(v) != len(set(v)):
        raise PydanticCustomError('unique_list', 'List must be unique')
    return v


UniqueList = Annotated[List[T], AfterValidator(_validate_unique_list), Field(json_schema_extra={'uniqueItems': True})]
