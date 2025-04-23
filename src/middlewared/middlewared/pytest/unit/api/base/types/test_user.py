from pydantic import ValidationError
import pytest

from middlewared.api.base import BaseModel, GroupName


@pytest.mark.parametrize("value, error", [
    ("", "Must be at least 1 character in length"),
    ("-group", "Cannot start with"),
    ("group$", "Valid characters are:"),
    ("_abcd-1234.ABCD", None),
])
def test_group_name(value, error: str | None):
    class Model(BaseModel):
        group: GroupName

    if error:
        with pytest.raises(ValidationError) as ve:
            Model(group=value)
        assert ve.match(error)
    else:
        Model(group=value)
