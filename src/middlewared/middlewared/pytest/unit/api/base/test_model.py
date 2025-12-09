from pydantic import Field
import pytest

from middlewared.api.base import (BaseModel, Excluded, excluded_field, ForUpdateMetaclass, single_argument_args,
                                  single_argument_result, model_subset)
from middlewared.api.base.handler.accept import accept_params, validate_model
from middlewared.api.base.handler.result import serialize_result
from middlewared.api.v25_04_0.pool_snapshottask import PoolSnapshotTaskCron
from middlewared.service_exception import ValidationErrors


class Object(BaseModel):
    id: int
    name: str
    count: int = 0


class CreateObject(Object):
    id: Excluded = excluded_field()


class UpdateObject(CreateObject, metaclass=ForUpdateMetaclass):
    pass


class UpdateArgs(BaseModel):
    id: int
    data: UpdateObject


@pytest.mark.parametrize("data", [
    {},
    {"name": "Ivan"},
    {"count": 0},
    {"count": 1},
])
def test_for_update(data):
    assert accept_params(UpdateArgs, [1, data]) == [1, data]


def test_single_argument_args():
    @single_argument_args("param")
    class MethodArgs(BaseModel):
        name: str
        count: int = 1

    assert accept_params(MethodArgs, [{"name": "ivan"}]) == [{"name": "ivan", "count": 1}]


def test_single_argument_args_error():
    @single_argument_args("param")
    class MethodArgs(BaseModel):
        name: str
        count: int = 1

    with pytest.raises(ValidationErrors) as ve:
        accept_params(MethodArgs, [{"name": 1}])

    assert ve.value.errors[0].attribute == "param.name"


def test_single_argument_result():
    @single_argument_result
    class MethodResult(BaseModel):
        name: str
        count: int

    assert serialize_result(MethodResult, {"name": "ivan", "count": 1}, True, False) == {"name": "ivan", "count": 1}


def test_update_with_cron():
    class CreateObjectWithCron(BaseModel):
        schedule: PoolSnapshotTaskCron = Field(default_factory=PoolSnapshotTaskCron)

    class UpdateObjectWithCron(CreateObjectWithCron, metaclass=ForUpdateMetaclass):
        pass

    class UpdateWithCronArgs(BaseModel):
        id: int
        data: UpdateObjectWithCron

    assert accept_params(UpdateWithCronArgs, [1, {}]) == [1, {}]


def test_update_with_alias():
    class CreateObjectWithAlias(BaseModel):
        pass_: str = Field(alias="pass")

    class UpdateObjectWithAlias(CreateObjectWithAlias, metaclass=ForUpdateMetaclass):
        pass

    class UpdateWithAliasArgs(BaseModel):
        id: int
        data: UpdateObjectWithAlias

    assert accept_params(UpdateWithAliasArgs, [1, {"pass": "1"}]) == [1, {"pass": "1"}]


class ModelSubsetTest(BaseModel, metaclass=ForUpdateMetaclass):
    b2_chunk_size: int = Field(alias="chunk_size", default=10)
    dropbox_chunk_size: int = Field(alias="chunk_size", default=20)
    fast_list: bool = False


@pytest.mark.parametrize("fields,data,result", [
    (["b2_chunk_size"], {}, {"chunk_size": 10}),
    (["dropbox_chunk_size"], {}, {"chunk_size": 20}),
    (["dropbox_chunk_size"], {"chunk_size": 25}, {"chunk_size": 25}),
    (["fast_list"], {}, {"fast_list": False}),
    (["fast_list"], {"fast_list": True}, {"fast_list": True}),
])
def test_model_subset(fields, data, result):
    assert validate_model(model_subset(ModelSubsetTest, fields), data) == result
