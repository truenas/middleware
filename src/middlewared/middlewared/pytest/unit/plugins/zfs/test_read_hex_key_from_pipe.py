import io
from types import SimpleNamespace

import pytest

from middlewared.plugins.zfs.encryption_keys import read_hex_key_from_pipe
from middlewared.service_exception import ValidationErrors


def pipe_job(data):
    return SimpleNamespace(
        check_pipe=lambda name: None, pipes=SimpleNamespace(input=SimpleNamespace(r=io.BytesIO(data)))
    )


@pytest.mark.parametrize(
    "data,expected",
    [
        (b"0" + b"a" * 63, "0" + "a" * 63),
        (b"A" * 64, "a" * 64),
    ],
)
def test_valid_key_is_read(data, expected):
    verrors = ValidationErrors()
    assert read_hex_key_from_pipe(pipe_job(data), verrors) == expected
    assert not verrors


@pytest.mark.parametrize("data", [b"0x" + b"a" * 62, b"g" * 64, b"a" * 63])
def test_invalid_key_is_rejected(data):
    verrors = ValidationErrors()
    assert read_hex_key_from_pipe(pipe_job(data), verrors) is None
    assert "key_file" in verrors
