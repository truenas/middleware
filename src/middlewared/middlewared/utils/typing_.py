from types import UnionType
from typing import Union

def is_union(type_: type) -> bool:
    return type_ is UnionType or type_ is Union
