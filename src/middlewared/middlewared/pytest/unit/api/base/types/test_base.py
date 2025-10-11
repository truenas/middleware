from contextlib import nullcontext

from pydantic import Secret
import pytest

from middlewared.api.base import BaseModel, LongString, TimeString
from middlewared.api.base.handler.accept import accept_params
from middlewared.service_exception import ValidationErrors


@pytest.mark.parametrize("type,value,error", [
    (str, "0" * 2000, "String should have at most 1024 characters")
])
def test_base_types(type, value, error):
    class Model(BaseModel):
        param: type

    with pytest.raises(ValidationErrors) as ve:
        assert accept_params(Model, [value])

    assert ve.value.errors[0].errmsg == error


class LongStringMethodArgs(BaseModel):
    str: LongString
    dict: "LongStringDict"


class LongStringDict(BaseModel):
    str: LongString
    list: list[LongString]


def test_long_string():
    data = ["test1" * 1000, {"str": "test2" * 1000, "list": ["test3" * 1000, "test4" * 1000]}]
    assert accept_params(LongStringMethodArgs, data) == data


class SecretLongStringMethodArgs(BaseModel):
    password: Secret[LongString]


def test_secret_long_string():
    assert accept_params(SecretLongStringMethodArgs, ["test"]) == ["test"]


class LongStringDefaultMethodArgs(BaseModel):
    str: LongString = ""


def test_long_string_default():
    assert accept_params(LongStringDefaultMethodArgs, []) == [""]


class TimeStringModel(BaseModel):
    field: TimeString


@pytest.mark.parametrize("arg, result", [
    ("1:00", "01:00"),
    ("13:3", "13:03"),
    ("23:59", "23:59"),
    ("25:00", None),  # hours >= 24
    ("23:59:59", None),  # seconds not supported
    ("1f:00", None)  # non-digit character
])
def test_time_string(arg, result):
    with pytest.raises(ValidationErrors) if result is None else nullcontext():
        assert accept_params(TimeStringModel, [arg]) == [result]
