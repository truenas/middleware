import pytest

from middlewared.utils import are_indices_in_consecutive_order


@pytest.mark.parametrize(
    'values,should_pass',
    [
        ([1, 3, 2], False),
        ([1, 3], False),
        ([1, 2, 3], True),
        ([5, 4, 3], False),
        ([], True),
        ([1], True),
    ]
)
def test_are_indices_in_consecutive_order(values, should_pass):
    assert are_indices_in_consecutive_order(values) == should_pass
