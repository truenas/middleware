"""Regression test for locals disclosure via JSON-RPC error tracebacks."""

import errno
import json
import sys
from unittest.mock import Mock

import pytest

from middlewared.api.base.server.ws_handler.rpc import RpcWebSocketApp
from middlewared.apps.websocket_app import WebSocketApplication

SECRET_API_KEY = "1-THISVALUEMUSTNEVERAPPEARINANERRORRESPONSE"


def _exc_info_carrying_secret():
    """Raise an exception from frames whose locals hold ``SECRET_API_KEY``."""

    def login_with_api_key(api_key):
        raise ValueError("boom")

    def dispatch(params):
        return login_with_api_key(params[0])

    try:
        dispatch([SECRET_API_KEY])
    except ValueError:
        return sys.exc_info()


@pytest.fixture
def rpc_app():
    # truenas_error_traceback / format_truenas_error do not need a fully constructed
    # app; bypass __init__ and supply only what format_truenas_error may touch.
    app = object.__new__(RpcWebSocketApp)
    app.middleware = Mock()
    app.py_exceptions = False
    return app


def test_truenas_error_traceback_omits_frames(rpc_app):
    trace = rpc_app.truenas_error_traceback(_exc_info_carrying_secret())

    assert "frames" not in trace
    # The fields that remain are the ones clients actually consume / that are safe.
    assert trace["class"] == "ValueError"
    assert isinstance(trace["formatted"], str) and trace["formatted"]


def test_truenas_error_traceback_does_not_leak(rpc_app):
    trace = rpc_app.truenas_error_traceback(_exc_info_carrying_secret())

    assert SECRET_API_KEY not in json.dumps(trace)


def test_format_truenas_error_payload_does_not_leak(rpc_app):
    # The full error `data` payload that gets sent to the client.
    payload = rpc_app.format_truenas_error(errno.EBUSY, "Rate Limit Exceeded", _exc_info_carrying_secret(), None)

    assert "frames" not in payload["trace"]
    assert SECRET_API_KEY not in json.dumps(payload)


def test_legacy_websocket_tb_error_does_not_leak():
    app = object.__new__(WebSocketApplication)

    trace = app._tb_error(_exc_info_carrying_secret())

    assert "frames" not in trace
    assert SECRET_API_KEY not in json.dumps(trace)
