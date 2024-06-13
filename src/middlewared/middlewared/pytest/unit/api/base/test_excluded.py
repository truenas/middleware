import pytest

from middlewared.api.base import BaseModel, excluded, excluded_field
from middlewared.api.base.handler.accept import accept_params
from middlewared.service_exception import ValidationErrors


class Object(BaseModel):
    id: int
    name: str


class CreateObject(Object):
    id: excluded() = excluded_field()


class CreateArgs(BaseModel):
    data: CreateObject


def test_excluded_field():
    with pytest.raises(ValidationErrors) as ve:
        accept_params(CreateObject, [{"id": 1, "name": "Ivan"}])

    assert ve.value.errors[0].attribute == "id"
    assert ve.value.errors[0].errmsg == "Extra inputs are not permitted"
