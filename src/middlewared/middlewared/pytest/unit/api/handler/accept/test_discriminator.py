from typing import Annotated, Literal

from pydantic import Discriminator
import pytest

from middlewared.api.base import BaseModel, LongNonEmptyString
from middlewared.api.base.handler.accept import accept_params
from middlewared.service_exception import ValidationErrors


class Provider1(BaseModel):
    type: Literal["PROVIDER1"]
    credentials1: LongNonEmptyString


class Provider2(BaseModel):
    type: Literal["PROVIDER2"]
    credentials2: LongNonEmptyString


class DiscriminatorMethodArgs(BaseModel):
    data: Annotated[Provider1 | Provider2, Discriminator("type")]


def test_discriminator_error():
    with pytest.raises(ValidationErrors) as ve:
        accept_params(DiscriminatorMethodArgs, [{}])

    assert {e.attribute: e.errmsg for e in ve.value.errors} == {"data.type": "Field required"}
