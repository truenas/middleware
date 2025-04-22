import pytest

from middlewared.api.base import BaseModel, GroupName
from middlewared.service_exception import ValidationErrors


@pytest.mark.parametrize("value, error", [
    ("", "Must be at least 1 character in length"),
    ("-group", "Cannot start with \"-\""),
    ("$group", "Valid characters are:"),
    ("_abcd-1234.ABCD", None),
])
def test_group_name(value, error: str | None):
    class Model(BaseModel):
        group: GroupName

    if error:
        with pytest.raises(ValidationErrors) as ve:
            Model(group=value)
        assert error in ve.value.errors[0].errmsg
    else:
        Model(group=value)
