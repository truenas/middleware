from typing import Annotated, Literal, Union

from pydantic import Discriminator, Field, Secret
import pytest

from middlewared.api.base import BaseModel, ForUpdateMetaclass, single_argument_args, single_argument_result
from middlewared.api.base.handler.accept import accept_params
from middlewared.api.base.handler.dump_params import dump_params
from middlewared.api.base.handler.result import serialize_result
from middlewared.api.base.handler.remove_secrets import remove_secrets


@pytest.mark.parametrize("expose_secrets,result", [
    (True, {"name": "ivan", "password": "pass"}),
    (False, {"name": "ivan", "password": "********"}),
])
def test_private_str(expose_secrets, result):
    @single_argument_result
    class MethodResult(BaseModel):
        name: str
        password: Secret[str]

    assert serialize_result(MethodResult, {"name": "ivan", "password": "pass"}, expose_secrets, False) == result


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


def test_remove_secrets_type_discriminator():
    class FTPCredentialsModel(BaseModel):
        type: Literal["FTP"]
        user: Secret[str]
        pass_: Secret[str] = Field(alias="pass")

    class WebDAVCredentialsModel(BaseModel):
        type: Literal["WEBDAV"]
        url: Secret[str]

    class ConnectionModel(BaseModel):
        name: str
        provider: Annotated[
            Union[FTPCredentialsModel, WebDAVCredentialsModel],
            Discriminator("type"),
        ]

    assert remove_secrets(ConnectionModel, {
        "name": "Test",
        "provider": {
            "type": "FTP",
            "user": "john",
            "pass": "password",
        },
    }) == {
        "name": "Test",
        "provider": {
            "type": "FTP",
            "user": "********",
            "pass": "********",
        },
    }


def test_private_union():
    with pytest.raises(TypeError) as ve:
        class UserModel(BaseModel):
            username: str
            password: Secret[str] | None

    assert ve.value.args[0] == ("Model UserModel has field password defined as Optional[pydantic.types.Secret[str]]. "
                                "pydantic.types.Secret[str] cannot be a member of an Optional or a Union, please make "
                                "the whole field Private.")


def test_remove_secrets_optional_model():
    """Test that secrets are removed from Optional[Model] fields"""
    class CredentialsModel(BaseModel):
        username: str
        password: Secret[str]

    class SystemModel(BaseModel):
        name: str
        credentials: CredentialsModel | None

    # Test with value present
    assert remove_secrets(SystemModel, {
        "name": "Test",
        "credentials": {
            "username": "john",
            "password": "secret123",
        },
    }) == {
        "name": "Test",
        "credentials": {
            "username": "john",
            "password": "********",
        },
    }

    # Test with None value
    assert remove_secrets(SystemModel, {
        "name": "Test",
        "credentials": None,
    }) == {
        "name": "Test",
        "credentials": None,
    }


def test_remove_secrets_non_discriminated_union():
    """Test that secrets are removed from non-discriminated Union types"""
    class FTPCredentialsModel(BaseModel):
        protocol: Literal["FTP"]
        user: Secret[str]

    class SSHCredentialsModel(BaseModel):
        protocol: Literal["SSH"]
        key: Secret[str]

    class ConnectionModel(BaseModel):
        name: str
        # Non-discriminated union - no Discriminator annotation
        credentials: Union[FTPCredentialsModel, SSHCredentialsModel]

    # Without discriminator, it should try the first matching model
    assert remove_secrets(ConnectionModel, {
        "name": "Test",
        "credentials": {
            "protocol": "FTP",
            "user": "john",
        },
    }) == {
        "name": "Test",
        "credentials": {
            "protocol": "FTP",
            "user": "********",
        },
    }


def test_remove_secrets_extra_fields():
    """Test that extra fields in value are preserved"""
    class UserModel(BaseModel):
        username: str
        password: Secret[str]

    # Value has extra fields not in model
    result = remove_secrets(UserModel, {
        "username": "john",
        "password": "secret123",
        "extra_field": "should_be_kept",
        "another_extra": {"nested": "data"},
    })

    assert result == {
        "username": "john",
        "password": "********",
        # Extra fields should be dropped since they're not in the model
    }


def test_remove_secrets_dict_of_models():
    """Test that secrets are removed from dict[str, Model] fields"""
    class CredentialsModel(BaseModel):
        username: str
        password: Secret[str]

    class SystemModel(BaseModel):
        name: str
        users: dict[str, CredentialsModel]

    assert remove_secrets(SystemModel, {
        "name": "Test",
        "users": {
            "admin": {
                "username": "admin",
                "password": "admin123",
            },
            "user": {
                "username": "user",
                "password": "user123",
            },
        },
    }) == {
        "name": "Test",
        "users": {
            "admin": {
                "username": "admin",
                "password": "********",
            },
            "user": {
                "username": "user",
                "password": "********",
            },
        },
    }


def test_remove_secrets_list_in_union():
    """Test that secrets are removed from list of models in a union"""
    class ItemModel(BaseModel):
        name: str
        secret: Secret[str]

    class ContainerModel(BaseModel):
        items: list[ItemModel] | None

    assert remove_secrets(ContainerModel, {
        "items": [
            {"name": "item1", "secret": "secret1"},
            {"name": "item2", "secret": "secret2"},
        ],
    }) == {
        "items": [
            {"name": "item1", "secret": "********"},
            {"name": "item2", "secret": "********"},
        ],
    }


def test_remove_secrets_deeply_nested():
    """Test deeply nested structures with secrets"""
    class InnerModel(BaseModel):
        value: str
        secret: Secret[str]

    class MiddleModel(BaseModel):
        inner: InnerModel
        items: list[InnerModel]

    class OuterModel(BaseModel):
        middle: MiddleModel

    assert remove_secrets(OuterModel, {
        "middle": {
            "inner": {
                "value": "test",
                "secret": "secret1",
            },
            "items": [
                {"value": "a", "secret": "secret2"},
                {"value": "b", "secret": "secret3"},
            ],
        },
    }) == {
        "middle": {
            "inner": {
                "value": "test",
                "secret": "********",
            },
            "items": [
                {"value": "a", "secret": "********"},
                {"value": "b", "secret": "********"},
            ],
        },
    }


def test_remove_secrets_union_with_none_in_discriminated():
    """Test discriminated union where value can be None"""
    class FTPModel(BaseModel):
        type: Literal["FTP"]
        password: Secret[str]

    class SSHModel(BaseModel):
        type: Literal["SSH"]
        key: Secret[str]

    class ConfigModel(BaseModel):
        connection: Annotated[Union[FTPModel, SSHModel], Discriminator("type")] | None

    # Test with value
    assert remove_secrets(ConfigModel, {
        "connection": {
            "type": "FTP",
            "password": "secret",
        },
    }) == {
        "connection": {
            "type": "FTP",
            "password": "********",
        },
    }

    # Test with None
    assert remove_secrets(ConfigModel, {
        "connection": None,
    }) == {
        "connection": None,
    }
