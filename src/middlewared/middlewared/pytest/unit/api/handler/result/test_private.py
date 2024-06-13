import pytest

from middlewared.api.base import BaseModel, ForUpdateMetaclass, Private, single_argument_args, single_argument_result
from middlewared.api.base.handler.accept import accept_params
from middlewared.api.base.handler.result import serialize_result


@pytest.mark.parametrize("expose_secrets,result", [
    (True, {"name": "ivan", "password": "pass"}),
    (False, {"name": "ivan", "password": "********"}),
])
def test_private_str(expose_secrets, result):
    @single_argument_result
    class MethodResult(BaseModel):
        name: str
        password: Private[str]

    assert serialize_result(MethodResult, {"name": "ivan", "password": "pass"}, expose_secrets) == result


@pytest.mark.parametrize("args", [[{}], [{"password": "xxx"}]])
def test_private_update(args):
    @single_argument_args("data")
    class UpdateArgs(BaseModel, metaclass=ForUpdateMetaclass):
        password: Private[str]

    assert accept_params(UpdateArgs, args) == args
