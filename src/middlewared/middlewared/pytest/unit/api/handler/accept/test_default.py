from pydantic import Field

from middlewared.api.base import BaseModel
from middlewared.api.base.handler.accept import accept_params


def test_default_dict():
    class Options(BaseModel):
        force: bool = False

    class MethodArgs(BaseModel):
        id: int
        options: Options = Field(default=Options())

    assert accept_params(MethodArgs, [1, {"force": True}]) == [1, {"force": True}]
    assert accept_params(MethodArgs, [1]) == [1, {"force": False}]
