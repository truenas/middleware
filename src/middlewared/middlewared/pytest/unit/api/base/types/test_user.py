import pytest

from middlewared.api.base import BaseModel, GroupName
from middlewared.service_exception import ValidationErrors


@pytest.mark.parametrize("value, error", [
    ("0" * 2000, "String should have at most 1024 characters")
])
def test_base_types(value, error):
    class Model(BaseModel):
        group: GroupName

    with pytest.raises(ValidationErrors) as ve:
        Model(group=value)

    assert ve.value.errors[0].errmsg == error
