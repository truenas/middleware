import contextlib
import pytest

from middlewared.test.integration.assets.privilege import privilege
from middlewared.test.integration.utils import client


@pytest.mark.parametrize('offset,limit', [
    (0, 4),
    (1, 4),
    (2, 4),
    (3, 4),
    (2, 5),
    (3, 5),
])
def test_query_filters(offset, limit):
    with contextlib.ExitStack() as stack:
        for i in range(5):
            stack.enter_context(
                privilege({
                    'name': f'Test Privilege {i}',
                    'web_shell': False
                })
            )
        with client() as c:
            query_results = c.call('privilege.query', [], {'select': ['id']})
            expected_result = query_results[offset:offset + limit]
            actual_result = c.call('privilege.query', [], {'offset': offset, 'limit': limit, 'select': ['id']})
            assert actual_result == expected_result
