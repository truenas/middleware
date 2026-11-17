import pytest

from middlewared.api.base import NQN, BaseModel
from middlewared.api.base.handler.accept import accept_params
from middlewared.service_exception import ValidationErrors


class NQNModel(BaseModel):
    nqn: NQN


@pytest.mark.parametrize(
    "value",
    [
        "nqn.2014-08.org.nvmexpress.discovery",
        "nqn.2014-08.org.nvmexpress:uuid:11111111-2222-3333-4444-555555555555",
        "nqn.2011-06.com.truenas:subsys1",
        "nqn.2011-06.com.truenas:a..b c",
    ],
)
def test_nqn_accepts(value):
    assert accept_params(NQNModel, [value]) == [value]


@pytest.mark.parametrize(
    "value",
    [
        "nqn.2011-06.com.truenas:poc/../../../../../../tmp/MARKER",  # path traversal
        "nqn.2011-06.com.truenas:a/b",
        "nqn.2011-06.com.truenas:a\nb",
        "nqn.2011-06.com.truenas:a\0b",
    ],
)
def test_nqn_rejects(value):
    with pytest.raises(ValidationErrors):
        accept_params(NQNModel, [value])
