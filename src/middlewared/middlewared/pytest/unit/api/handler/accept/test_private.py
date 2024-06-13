from middlewared.api.base import BaseModel, Private
from middlewared.api.base.handler.accept import accept_params


def test_private_str():
    class MethodArgs(BaseModel):
        password: Private[str]

    assert accept_params(MethodArgs, ["pass"]) == ["pass"]
