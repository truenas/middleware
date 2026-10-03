from pydantic import ValidationError
import pytest

from middlewared.api.current import ZFSResourceCreateProperties, ZFSResourceSetProperties


def test_set_accepts_auto_refreservation():
    assert ZFSResourceSetProperties(refreservation="auto").refreservation == "auto"


def test_set_parses_refreservation_size():
    assert ZFSResourceSetProperties(refreservation="1G").refreservation == 1073741824


@pytest.mark.parametrize(
    "properties",
    [{"refreservation": "auto"}],
)
def test_create_rejects(properties):
    with pytest.raises(ValidationError) as exc_info:
        ZFSResourceCreateProperties(**properties)
    assert exc_info.value.errors()[0]["loc"][0] == next(iter(properties))
