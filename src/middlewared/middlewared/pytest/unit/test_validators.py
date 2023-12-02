import pytest

from middlewared.validators import Email


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
