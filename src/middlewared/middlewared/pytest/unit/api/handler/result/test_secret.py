from pydantic import Secret
import pytest

from middlewared.api.base import BaseModel, ForUpdateMetaclass, single_argument_args, single_argument_result
from middlewared.api.base.handler.accept import accept_params
from middlewared.api.base.handler.dump_params import dump_params, remove_secrets
from middlewared.api.base.handler.result import serialize_result


@pytest.mark.parametrize("expose_secrets,result", [
    (True, {"name": "ivan", "password": "pass"}),
    (False, {"name": "ivan", "password": "********"}),
])
def test_private_str(expose_secrets, result):
    @single_argument_result
    class MethodResult(BaseModel):
        name: str
        password: Secret[str]

    assert serialize_result(MethodResult, {"name": "ivan", "password": "pass"}, expose_secrets) == result


@pytest.mark.parametrize("args", [[{}], [{"password": "xxx"}]])
def test_private_update(args):
    @single_argument_args("data")
    class UpdateArgs(BaseModel, metaclass=ForUpdateMetaclass):
        password: Secret[str]

    assert accept_params(UpdateArgs, args) == args


@pytest.mark.parametrize("args,result", [
    ({"username": "ivan", "password": "xxx"}, {"username": "ivan", "password": "********"}),
    ({"username": 1, "password": "xxx"}, {"username": 1, "password": "********"}),
    ({"password": "xxx"}, {"password": "********"}),
])
def test_private_without_validation(args, result):
    @single_argument_args("data")
    class CreateArgs(BaseModel):
        username: str
        password: Secret[str]

    assert dump_params(CreateArgs, [args], False) == [result]


def test_remove_secrets_nested():
    class UserModel(BaseModel):
        username: str
        password: Secret[str]

    class SystemModel(BaseModel):
        users: list[UserModel]

    assert remove_secrets(SystemModel, {
        "users": [
            {"username": "ivan", "password": "xxx"},
            {"username": "oleg", "password": "xxx"},
        ],
    }) == {
        "users": [
            {"username": "ivan", "password": "********"},
            {"username": "oleg", "password": "********"},
        ],
    }


def test_private_union():
    with pytest.raises(TypeError) as ve:
        class UserModel(BaseModel):
            username: str
            password: Secret[str] | None

    assert ve.value.args[0] == ("Model UserModel has field password defined as Optional[pydantic.types.Secret[str]]. "
                                "pydantic.types.Secret[str] cannot be a member of an Optional or a Union, please make "
                                "the whole field Private.")
