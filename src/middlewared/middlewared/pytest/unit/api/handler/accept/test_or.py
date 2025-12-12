from typing import Literal

import pytest

from middlewared.api.base import BaseModel, HttpUrl
from middlewared.api.base.handler.accept import accept_params
from middlewared.service_exception import ValidationErrors


class Provider(BaseModel):
    endpoint: Literal[""] | HttpUrl


def test_discriminator_error():
    with pytest.raises(ValidationErrors) as ve:
        accept_params(Provider, ["google.com"])

    assert {e.attribute: e.errmsg for e in ve.value.errors} == {
        "endpoint": "Input should be '' or Input should be a valid URL, relative URL without a base"
    }
