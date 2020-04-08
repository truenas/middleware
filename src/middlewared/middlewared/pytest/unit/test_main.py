# -*- coding=utf-8 -*-
import asyncio
import json
import logging
from unittest.mock import Mock, patch

from asyncmock import AsyncMock  # FIXME: python 3.8
import pytest

from middlewared.main import Application, Middleware
from middlewared.service import accepts, job, CoreService, CRUDService
from middlewared.plugins.datastore.read import DatastoreService
from middlewared.schema import Dict, Str


class MockService(CRUDService):
    @accepts(Dict("test_create", Str("password", private=True)))
    async def do_create(self, args):
        raise Exception()

    @accepts(Dict("op", Str("password", private=True)))
    async def op(self, args):
        raise Exception()


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["create", "op"])
async def test__normal_service(caplog, method):
    caplog.set_level(logging.INFO)

    with patch("middlewared.main.multiprocessing"):
        middleware = Middleware()
    middleware.loop = asyncio.get_event_loop()
    middleware.add_service(MockService(middleware))

    fut = asyncio.Future()
    application = Application(middleware, asyncio.get_event_loop(), Mock(), Mock(send_str=AsyncMock(side_effect=fut.set_result)))
    application.authenticated = True
    application.handshake = True
    await application.on_message({"id": "1", "msg": "method", "method": f"mock.{method}", "params": [{"password": "secret"}]})
    await fut

    assert any(
        f"Exception while calling mock.{method}(*[{{'password': '********'}}])" in record.message
        for record in caplog.get_records("call")
    )


class JobService(CRUDService):
    @accepts(Dict("test_create", Str("password", private=True)))
    @job()
    async def do_create(self, job, args):
        raise Exception()

    @accepts(Dict("op", Str("password", private=True)))
    @job()
    async def op(self, job, args):
        raise Exception()


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["create", "op"])
async def test__job_service(caplog, method):
    caplog.set_level(logging.INFO)

    with patch("middlewared.main.multiprocessing"):
        middleware = Middleware()
    middleware.loop = asyncio.get_event_loop()
    middleware.add_service(CoreService(middleware))
    middleware.add_service(DatastoreService(middleware))
    middleware.add_service(JobService(middleware))
    middleware._resolve_methods()

    fut = asyncio.Future()
    application = Application(middleware, asyncio.get_event_loop(), Mock(), Mock(send_str=AsyncMock(side_effect=fut.set_result)))
    application.authenticated = True
    application.handshake = True
    await application.on_message({"id": "1", "msg": "method", "method": f"job.{method}", "params": [{"password": "secret"}]})
    await fut

    fut = asyncio.Future()
    application.response.send_str = AsyncMock(side_effect=fut.set_result)
    await application.on_message({"id": "1", "msg": "method", "method": "core.get_jobs", "params": []})
    result = json.loads(await fut)

    assert result["result"][0]["arguments"] == [{"password": "********"}]
