import pytest

from middlewared.api.base.server.ws_handler.rpc import RpcWebSocketHandler


@pytest.mark.parametrize(
    "ws_msg, should_raise_value_error",
    [
        # test "id" member
        (
            {"id": 1, "method": "test.method", "jsonrpc": "2.0", "params": ["a", "b"]},
            False,
        ),
        (
            {
                "id": "1",
                "method": "test.method",
                "jsonrpc": "2.0",
                "params": ["a", "b"],
            },
            False,
        ),
        (
            {
                "id": None,
                "method": "test.method",
                "jsonrpc": "2.0",
                "params": ["a", "b"],
            },
            False,
        ),
        (
            {
                "id": ["bad"],
                "method": "test.method",
                "jsonrpc": "2.0",
                "params": ["a", "b"],
            },
            True,
        ),
        ({"method": "test.method", "jsonrpc": "2.0", "params": ["a", "b"]}, True),
        # test "method" member
        ({"id": 1, "method": [], "jsonrpc": "2.0", "params": ["a", "b"]}, True),
        ({"id": 1, "method": "", "jsonrpc": "2.0", "params": ["a", "b"]}, True),
        ({"id": 1, "method": None, "jsonrpc": "2.0", "params": ["a", "b"]}, True),
        ({"id": 1, "jsonrpc": "2.0", "params": ["a", "b"]}, True),
        # test "jsonrpc" member
        (
            {"id": 1, "method": "test.method", "jsonrpc": "1.0", "params": ["a", "b"]},
            True,
        ),
        (
            {"id": 1, "method": "test.method", "jsonrpc": None, "params": ["a", "b"]},
            True,
        ),
        (
            {
                "id": 1,
                "method": "test.method",
                "jsonrpc": ["bad"],
                "params": ["a", "b"],
            },
            True,
        ),
        (
            {"id": 1, "method": "test.method", "jsonrpc": [""], "params": ["a", "b"]},
            True,
        ),
        ({"id": 1, "method": "test.method", "jsonrpc": [], "params": ["a", "b"]}, True),
        ({"id": 1, "method": "test.method", "params": ["a", "b"]}, True),
        # test "params" member
        (
            {"id": 1, "method": "test.method", "jsonrpc": "2.0", "params": ["a", "b"]},
            False,
        ),
        ({"id": 1, "method": "test.method", "jsonrpc": "2.0", "params": []}, False),
        ({"id": 1, "method": "test.method", "jsonrpc": "2.0"}, False),
        ({"id": 1, "method": "test.method", "jsonrpc": "2.0", "params": 1}, True),
        ({"id": 1, "method": "test.method", "jsonrpc": "2.0", "params": "bad"}, True),
        ({"id": 1, "method": "test.method", "jsonrpc": "2.0", "params": None}, True),
        # fuzzy
        ("", True),
        ({}, True),
        (None, True),
        ([], True),
        (["bad"], True),
        (b"bad", True),
    ],
)
@pytest.mark.asyncio
async def test_validate_message(ws_msg, should_raise_value_error):
    if should_raise_value_error:
        with pytest.raises(ValueError):
            RpcWebSocketHandler.validate_message(ws_msg)
    else:
        RpcWebSocketHandler.validate_message(ws_msg)
