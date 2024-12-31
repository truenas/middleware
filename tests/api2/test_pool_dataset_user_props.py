import pytest

from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call


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
