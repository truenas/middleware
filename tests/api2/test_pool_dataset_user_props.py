import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call


def test_pool_dataset_create_applies_user_props():
    user_props = [
        {'key': 'org.truenas.test:first', 'value': 'one'},
        {'key': 'org.truenas.test:second', 'value': 'two'},
    ]
    with dataset('create_user_props', data={'user_properties': user_props}) as ds:
        result = call(
            'pool.dataset.query',
            [['id', '=', ds]],
            {'get': True, 'extra': {'properties': [], 'retrieve_user_props': True}}
        )
        for prop in user_props:
            assert result['user_properties'].get(prop['key'], {}).get('value') == prop['value'], result

        # `comments` defaults to "INHERIT", which must not be written out as a property
        assert 'comments' not in result['user_properties'], result


@pytest.mark.parametrize('user_props, error', [
    (
        [{'key': 'org.freenas:description', 'value': 'overwritten'}],
        "'org.freenas:description' is managed by TrueNAS, use the 'comments' field to set it",
    ),
    (
        [{'key': 'org.truenas.test:invalid name', 'value': 'one'}],
        'is not a valid ZFS user property name',
    ),
    (
        [{'key': 'org.truenas.test:dupe', 'value': 'one'}, {'key': 'org.truenas.test:dupe', 'value': 'two'}],
        'is specified more than once',
    ),
])
def test_pool_dataset_create_rejects_bad_user_props(user_props, error):
    with pytest.raises(ValidationErrors, match=error):
        with dataset('bad_user_props', data={'user_properties': user_props}):
            pass


@pytest.mark.parametrize('user_props', [True, False])
def test_pool_dataset_query_user_props_true_false(user_props):
    with dataset("query_test") as ds:
        result = call(
            "pool.dataset.query",
            [["id", "=", ds]],
            {"extra": {"flat": False, "properties": [], "retrieve_user_props": user_props}}
        )
        if user_props:
            assert "user_properties" in result[0], f"'user_properties' not found in result: {result}"
        else:
            assert "user_properties" not in result[0], f"'user_properties' found in result: {result}"
