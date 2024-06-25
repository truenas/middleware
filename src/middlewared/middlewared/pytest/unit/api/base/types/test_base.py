import pytest

from middlewared.api.base import BaseModel, LongString
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
