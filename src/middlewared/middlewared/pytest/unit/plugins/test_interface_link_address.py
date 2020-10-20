# -*- coding=utf-8 -*-
import logging
from unittest.mock import ANY

from asyncmock import AsyncMock
import pytest
import sqlalchemy as sa

from middlewared.plugins.interface.link_address import setup as link_address_setup
from middlewared.pytest.unit.plugins.test_datastore import Model, datastore_test

logger = logging.getLogger(__name__)


class InterfaceModel(Model):
    __tablename__ = "network_interfaces"

    id = sa.Column(sa.Integer(), primary_key=True)
    int_interface = sa.Column(sa.Integer(), nullable=False)
    int_link_address = sa.Column(sa.String(17), nullable=True)
    int_settings = sa.Column(sa.Integer())


@pytest.mark.parametrize("test", [
    # (
    #     Hardware interfaces
    #     Interfaces in database BEFORE (marked by settings ID)
    #     Interfaces in database AFTER (marked by settings ID)
    # )
    (
        [("eth0", "08:00:27:1e:9f:d3"), ("eth1", "08:00:27:1e:9f:d4")],
        [("em0", "08:00:27:1e:9f:d4", 0), ("em1", "08:00:27:1e:9f:d3", 1)],
        [("eth0", "08:00:27:1e:9f:d3", 1), ("eth1", "08:00:27:1e:9f:d4", 0)],
    ),
    (
        [("eth0", "08:00:27:1e:9f:d3"), ("eth1", "08:00:27:1e:9f:d4")],
        [("eth0", None, 0), ("eth1", "08:00:27:1e:9f:d4", 1)],
        [("eth0", "08:00:27:1e:9f:d3", 0), ("eth1", "08:00:27:1e:9f:d4", 1)],
    ),
    (
        [("eth0", "08:00:27:1e:9f:d4")],
        [("em0", "08:00:27:1e:9f:d4", 0), ("eth0", "08:00:27:1e:9f:d4", 0)],
        [("em0", None, 0), ("eth0", "08:00:27:1e:9f:d4", 0)],
    ),
    (
        [("eth0", "08:00:27:1e:9f:d4")],
        [("em0", "08:00:27:1e:9f:d5", 0)],
        [("em0", None, 0)],
    ),
])
@pytest.mark.asyncio
async def test__interface_link_address_setup(test):
    real_interfaces, database, result = test

    async with datastore_test() as ds:
        query = ds.middleware["datastore.query"]

        async def mock_query(table, *args):
            if table in ["network.bridge", "network.lagginterfacemembers", "network.vlan"]:
                return []

            return await query(table, *args)

        ds.middleware["datastore.query"] = mock_query

        for interface, link_address, settings in database:
            await ds.insert("network.interfaces", {
                "interface": interface,
                "link_address": link_address,
                "settings": settings,
            }, {"prefix": "int_"})

        ds.middleware["interface.query"] = AsyncMock(return_value=[
            {
                "name": name,
                "state": {
                    "link_address": link_address,
                }
            }
            for name, link_address in real_interfaces
        ])

        await link_address_setup(ds.middleware)

        def key(v):
            return v["interface"]
        assert sorted(await ds.query("network.interfaces", [], {"prefix": "int_"}), key=key) == sorted([
            {
                "id": ANY,
                "interface": interface,
                "link_address": link_address,
                "settings": settings,
            }
            for interface, link_address, settings in result
        ], key=key)
