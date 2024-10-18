import pytest

from middlewared.plugins.apps.schema_utils import get_list_item_from_value
from middlewared.schema import List


@pytest.mark.parametrize('values, question_attr, should_work', [
    (
        ['val1', 'val2', 'val3'],
        List(
            items=[
                List({'question1': 'desc1'}),
                List({'question2': 'desc2'}),
                List({'question3': 'desc3'})
            ]
        ),
        True
    ),
    (
        None,
        List(
            items=[
                List({'question1': 'desc1'}),
                List({'question2': 'desc2'}),
                List({'question3': 'desc3'})
            ]
        ),
        True
    ),
    (
        [{'val1': 'a'}, {'val2': 'b'}, {'val3': 'c'}],
        List(
            items=[
                List({'question1': 'desc1'}),
                List({'question2': 'desc2'}),
                List({'question3': 'desc3'})
            ]
        ),
        True
    ),
    (
        ['val1', 'val1'],
        List(
            items=[
                List({'question1': 'desc1'}, unique=True),
            ],
        ),
        False
    ),
])
def test_get_list_item_from_value(values, question_attr, should_work):
    if should_work:
        result = get_list_item_from_value(values, question_attr)
        assert result is not None
    else:
        assert get_list_item_from_value(values, question_attr) is None
