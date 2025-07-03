from pydantic import Field, PositiveInt
import pytest

from middlewared.api.base import BaseModel
from middlewared.api.base.handler.accept import accept_params
from middlewared.service_exception import ValidationErrors


class MethodArgs(BaseModel):
    param: "Param"
    force: bool = False


class Param(BaseModel):
    name: str
    count: PositiveInt = 1


@pytest.mark.parametrize("params,result_or_error", [
    ([], {"param": "Field required"}),
    ([1, 2, 3], {"": "Too many arguments (expected 2, found 3)"}),
    ([{"name": "test"}], [{"name": "test", "count": 1}, False]),
    ([{"name": "test"}, True], [{"name": "test", "count": 1}, True]),
    ([{"name": "test"}, 1], {"force": "Input should be a valid boolean"}),
    ([{"name": "test", "count": 0}], {"param.count": "Input should be greater than 0"}),
    ([{"name": "test", "amount": 0}], {"param.amount": "Extra inputs are not permitted"}),
])
def test__accept_params(params, result_or_error):
    if isinstance(result_or_error, list):
        assert accept_params(MethodArgs, params) == result_or_error
    elif isinstance(result_or_error, dict):
        with pytest.raises(ValidationErrors) as ve:
            accept_params(MethodArgs, params)

        assert {e.attribute: e.errmsg for e in ve.value.errors} == result_or_error


class AliasMethodArgs(BaseModel):
    query_filters: int = Field(alias="query-filters", default=1)


def test__accept_alias():
    assert accept_params(AliasMethodArgs, [1]) == [1]


def test__accept_alias_default():
    assert accept_params(AliasMethodArgs, []) == [1]
