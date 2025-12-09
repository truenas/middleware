from middlewared.api.base import BaseModel, single_argument_result
from middlewared.api.base.handler.result import serialize_result


def test_preserves_types():
    @single_argument_result
    class MethodResult(BaseModel):
        data: dict

    value = {
        "data": {
            "id": {1, 2, 3},
        },
    }

    assert serialize_result(MethodResult, value, False, False) == value
