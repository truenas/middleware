from pydantic import ValidationError
import pytest

from middlewared.api.current import ZFSResourceCreateProperties, ZFSResourceSetProperties


def test_set_accepts_auto_refreservation():
    assert ZFSResourceSetProperties(refreservation="auto").refreservation == "auto"


def test_set_parses_refreservation_size():
    assert ZFSResourceSetProperties(refreservation="1G").refreservation == 1073741824


@pytest.mark.parametrize(
    "properties",
    [
        {"refreservation": "auto"},
        {"quota": "auto"},
        {"volsize": "none"},
        {"copies": "2"},
        {"copies": 4},
        {"recordsize": "1.3K"},
    ],
)
def test_create_rejects(properties):
    with pytest.raises(ValidationError) as exc_info:
        ZFSResourceCreateProperties(**properties)
    assert exc_info.value.errors()[0]["loc"][0] == next(iter(properties))


@pytest.mark.parametrize(
    "properties, name, expected",
    [
        ({"quota": "none"}, "quota", 0),
        ({"refquota": "none"}, "refquota", 0),
        ({"refreservation": "none"}, "refreservation", 0),
        ({"volsize": "512M"}, "volsize", 536870912),
        ({"volblocksize": "16K"}, "volblocksize", 16384),
        ({"special_small_blocks": 0}, "special_small_blocks", 0),
        ({"copies": 2}, "copies", 2),
    ],
)
def test_create_normalises_sizes(properties, name, expected):
    assert getattr(ZFSResourceCreateProperties(**properties), name) == expected
