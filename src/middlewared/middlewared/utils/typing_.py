from types import UnionType
from typing import Any, Union


def is_union(type_: Any) -> bool:
    return type_ is UnionType or type_ is Union
