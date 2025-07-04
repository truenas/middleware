import os
from typing import Annotated, Literal

from pydantic import (
    AfterValidator, AnyUrl, BeforeValidator, ConfigDict, DirectoryPath, FilePath, PlainSerializer,
)

from middlewared.api.base import BaseModel as PydanticBaseModel, IPvAnyAddress  # noqa: F401


class BaseModel(PydanticBaseModel):
    """
    Base model that allows extra fields by default and have strict=False because we want maximum compatibility
    with existing implementation we have where the schema was loose enough to be catered to.
    """
    model_config = ConfigDict(
        extra='allow',
        strict=False,
    )


def _validate_absolute_path(value: str) -> str:
    if value == '':
        return value

    if not os.path.isabs(value):
        raise ValueError('Path must be absolute')

    return os.path.normpath(value.rstrip('/'))


def create_length_validated_type(base_type, min_length: int | None = None, max_length: int | None = None):
    """Create a type with length validation applied before the base type validation"""

    def validate_length(v):
        if isinstance(v, str):
            if min_length is not None and len(v) < min_length:
                raise ValueError(f'Value should have at least {min_length} items')
            if max_length is not None and len(v) > max_length:
                raise ValueError(f'Value should have at most {max_length} items')
        return v

    return Annotated[
        base_type,
        BeforeValidator(validate_length),
    ]


AbsolutePath = Annotated[
    str,
    AfterValidator(_validate_absolute_path),
]
HostPath = Annotated[
    Literal[''] | FilePath | DirectoryPath,
    PlainSerializer(lambda x: str(x), return_type=str)
]
URI = Annotated[
    Literal[''] | AnyUrl,
    PlainSerializer(lambda x: str(x), return_type=str),
]
