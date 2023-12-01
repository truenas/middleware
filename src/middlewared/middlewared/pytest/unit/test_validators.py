import pytest

from middlewared.schema import Dict, Int, Str
from middlewared.validators import validate_schema, Range, Email


@pytest.mark.parametrize("schema,data,result", [
    ([Str("text")], {"text": "XXX"}, {"text": "XXX"}),
    ([Str("text", default="XXX")], {}, {"text": "XXX"}),
    ([Str("text", required=True)], {}, {"text"}),
    ([Int("number")], {"number": "1"}, {"number": 1}),
    ([Int("number")], {"number": "XXX"}, {"number"}),
    ([Int("number", validators=[Range(min=2)])], {"number": 1}, {"number"}),
    ([Dict("image", Str("repository", required=True))], {}, {"image.repository"}),
])
def test__validate_schema(schema, data, result):
    verrors = validate_schema(schema, data)
    if isinstance(result, set):
        assert result == {e.attribute for e in verrors.errors}
    else:
        assert data == result


@pytest.mark.parametrize("email,should_raise", [
    ("2@2@me.com", False),
    ("2&2@me.com", False),
    ("2@\uD800\uD800ñoñó郵件ñoñó郵件.商務", False),
    (f'{"2" * 250}@me.com', True),
    ("@me.com", True),
    ("2@", True),
    ("@", True),
    ("", True),
])
def test__email_schema(email, should_raise):
    if not should_raise:
        Email()(email)
    else:
        with pytest.raises(ValueError):
            Email()(email)
