import pytest

from middlewared.utils.size import normalize_size


@pytest.mark.parametrize('input_value, expected', [
    ('2 GiB', 2 * 2**30),
    ('500 MiB', 500 * 2**20),
    ('100K', 100 * 10**3),
    ('10G', 10 * 10**9),
    ('1 TiB', 1 * 2**40),
    ('2P', 2 * 10**15),
    ('2 gib', 2 * 2**30),
    ('500 mIb', 500 * 2**20),
    ('100k', 100 * 10**3),
    ('123', 123),
    (1024, 1024),
    (3.14, 3.14),
    (None, None)
])
def test_normalize_size_valid(input_value, expected):
    assert normalize_size(input_value) == expected


@pytest.mark.parametrize('input_value', [
    'XYZ',
    '10 XB'
])
def test_normalize_size_invalid(input_value):
    with pytest.raises(ValueError, match=f'Invalid size format: {input_value}'):
        normalize_size(input_value)


@pytest.mark.parametrize('input_value', [
    'XYZ',
    '10 XB'
])
def test_normalize_size_invalid_no_exception(input_value):
    assert normalize_size(input_value, raise_exception=False) is None
