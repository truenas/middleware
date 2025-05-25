from typing import Annotated, Literal

from pydantic import AnyUrl, ConfigDict, IPvAnyAddress as PydanticIPvAnyAddress, PlainSerializer

from middlewared.api.base import BaseModel as PydanticBaseModel


class BaseModel(PydanticBaseModel):
    """
    Base model that allows extra fields by default and have strict=False because we want maximum compatibility
    with existing implementation we have where the schema was loose enough to be catered to.
    """
    model_config = ConfigDict(
        extra='allow',
        strict=False,
    )

IPvAnyAddress = Annotated[
    Literal[''] | PydanticIPvAnyAddress,
    PlainSerializer(lambda x: str(x), return_type=str),
]
URI = Annotated[
    Literal[''] | AnyUrl,
    PlainSerializer(lambda x: str(x), return_type=str),
]
