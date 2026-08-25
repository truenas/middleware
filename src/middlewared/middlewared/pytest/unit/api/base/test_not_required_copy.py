import copy
import pickle

from pydantic import Field
import pytest

from middlewared.api.base import BaseModel
from middlewared.api.base.model import NotRequired


class NotRequiredModel(BaseModel):
    required: str
    optional: str = Field(default=NotRequired)


class OuterModel(BaseModel):
    inner: NotRequiredModel


@pytest.mark.parametrize("clone", [copy.copy, copy.deepcopy, lambda v: pickle.loads(pickle.dumps(v))])
def test_sentinel_survives_cloning(clone):
    """`_not_required_serializer` filters unset fields by identity, so any clone of a model must still
    hold the `NotRequired` singleton, not a copy of it."""
    assert clone(NotRequired) is NotRequired


@pytest.mark.parametrize("clone", [copy.copy, copy.deepcopy, lambda v: pickle.loads(pickle.dumps(v))])
def test_cloned_model_excludes_unset_fields(clone):
    assert clone(NotRequiredModel(required="value")).model_dump() == {"required": "value"}


def test_deepcopied_nested_model_excludes_unset_fields():
    outer = copy.deepcopy(OuterModel(inner=NotRequiredModel(required="value")))
    assert outer.model_dump() == {"inner": {"required": "value"}}
