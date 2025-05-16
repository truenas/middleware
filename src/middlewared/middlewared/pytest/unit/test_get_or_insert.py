import unittest.mock

import pytest

from middlewared.pytest.unit.middleware import Middleware
from middlewared.service.config_service import ConfigService


@pytest.mark.parametrize('rows, new_row, should_work', [
    (
        [{'label': 'TRUENAS', 'preferred_trains': ['community', 'stable']}],
        {},
        True,
    ),
    (
        [],
        {'label': 'TRUENAS', 'preferred_trains': ['community', 'stable']},
        True
    ),
    (
        [],
        {},
        False
    )
])
@pytest.mark.asyncio
async def test_get_or_insert(rows, new_row, should_work):
    middleware = Middleware()
    middleware['datastore.query'] = lambda *args: rows
    middleware['datastore.insert'] = lambda *args: new_row
    middleware['datastore.config'] = lambda *args: new_row
    config_service_obj = ConfigService(middleware)

    if should_work:
        response = await config_service_obj._get_or_insert('service.catalog', {})
        if rows:
            assert response == rows[0]
        else:
            assert response == new_row
    else:
        query_mock = unittest.mock.Mock()
        query_mock.side_effect = IndexError
        with pytest.raises(IndexError):
            middleware['datastore.query'] = query_mock
            await config_service_obj._get_or_insert('service.catalog', {})
