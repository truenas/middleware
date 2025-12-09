from pydantic import Secret
import pytest

from middlewared.api.base import BaseModel
from middlewared.api.base.handler.result import serialize_result
from middlewared.service.crud_service import query_result


@pytest.mark.parametrize("result,serialized", [
    ([{"username": "ivan", "password": "pass"}, {"username": "pyotr", "password": "p@ss"}],
     [{"username": "ivan", "password": "********"}, {"username": "pyotr", "password": "********"}]),
    ({"username": "ivan", "password": "pass"}, {"username": "ivan", "password": "********"}),
    ({"username": "ivan"}, {"username": "ivan"}),
    (10, 10),
])
def test_query_result(result, serialized):
    class Entry(BaseModel):
        username: str
        password: Secret[str]

    assert serialize_result(query_result(Entry), result, False, False) == serialized
