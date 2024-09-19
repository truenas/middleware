from pydantic import Secret

from middlewared.api.base import BaseModel
from middlewared.api.base.handler.accept import accept_params


def test_private_str():
    class MethodArgs(BaseModel):
        password: Secret[str]

    assert accept_params(MethodArgs, ["pass"]) == ["pass"]
