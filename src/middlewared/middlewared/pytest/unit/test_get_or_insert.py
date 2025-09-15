import json
import unittest.mock

import pytest
import sqlalchemy as sa
from sqlalchemy import text

from middlewared.pytest.unit.middleware import Middleware
from middlewared.pytest.unit.plugins.test_datastore import datastore_test, Model
from middlewared.service.config_service import ConfigService


class CatalogModel(Model):
    __tablename__ = 'services_catalog'

    label = sa.Column(sa.String(255), nullable=False, unique=True, primary_key=True)
    preferred_trains = sa.Column(sa.JSON(list))


@pytest.mark.parametrize('rows, should_work', [
    (
        [{'label': 'TRUENAS', 'preferred_trains': ['community', 'stable']}],
        True,
    ),
    (
        [],
        True
    ),
    (
        [],
        False
    )
])
@pytest.mark.asyncio
async def test_get_or_insert(rows, should_work):
    async with datastore_test() as ds:
        middleware = Middleware()
        middleware['datastore.query'] = ds.query
        middleware['datastore.insert'] = ds.insert
        middleware['datastore.config'] = ds.config
        config_service_obj = ConfigService(middleware)

        if should_work:
            if rows:
                # Testing case where the row exists already
                ds.execute(
                    text('INSERT INTO `services_catalog` VALUES (:label, :trains)'),
                    {'label': rows[0]['label'], 'trains': json.dumps(rows[0]['preferred_trains'])}
                )
                response = await config_service_obj._get_or_insert('services.catalog', {})
                assert response == rows[0]
            else:
                # Testing case where the row does not exist and is added by config service
                # get_or_insert
                response = await config_service_obj._get_or_insert('services.catalog', {})
                assert response == {'label': '', 'preferred_trains': None}
        else:
            # Testing case where the row does exist but the query method raises some exception
            # in this case we say IndexError - so we make sure that we don't have datastore.insert
            # called in this case
            query_mock = unittest.mock.Mock(side_effect=IndexError)
            middleware['datastore.query'] = query_mock

            insert_mock = unittest.mock.Mock()
            config_mock = unittest.mock.Mock()
            middleware['datastore.insert'] = insert_mock
            middleware['datastore.config'] = config_mock

            with pytest.raises(IndexError):
                await config_service_obj._get_or_insert('service.catalog', {})

            insert_mock.assert_not_called()
            config_mock.assert_not_called()
