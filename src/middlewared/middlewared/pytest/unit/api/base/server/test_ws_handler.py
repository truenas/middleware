import pytest

from middlewared.api.base.server.ws_handler.rpc import RpcWebSocketHandler


@pytest.mark.parametrize(
    "ws_msg, error_type",
    [
        # test "id" member
        (
            {"id": 1, "method": "test.method", "jsonrpc": "2.0", "params": ["a", "b"]},
            None,
        ),
        (
            {
                "id": "1",
                "method": "test.method",
                "jsonrpc": "2.0",
                "params": ["a", "b"],
            },
            None,
        ),
        (
            {
                "id": None,
                "method": "test.method",
                "jsonrpc": "2.0",
                "params": ["a", "b"],
            },
            None,
        ),
        (
            {
                "id": ["bad"],
                "method": "test.method",
                "jsonrpc": "2.0",
                "params": ["a", "b"],
            },
            ValueError,
        ),
        # test "method" member
        ({"id": 1, "method": [], "jsonrpc": "2.0", "params": ["a", "b"]}, ValueError),
        ({"id": 1, "method": "", "jsonrpc": "2.0", "params": ["a", "b"]}, ValueError),
        ({"id": 1, "method": None, "jsonrpc": "2.0", "params": ["a", "b"]}, ValueError),
        ({"id": 1, "jsonrpc": "2.0", "params": ["a", "b"]}, ValueError),
        # test "jsonrpc" member
        (
            {"id": 1, "method": "test.method", "jsonrpc": "1.0", "params": ["a", "b"]},
            ValueError,
        ),
        (
            {"id": 1, "method": "test.method", "jsonrpc": None, "params": ["a", "b"]},
            ValueError,
        ),
        (
            {
                "id": 1,
                "method": "test.method",
                "jsonrpc": ["bad"],
                "params": ["a", "b"],
            },
            ValueError,
        ),
        (
            {"id": 1, "method": "test.method", "jsonrpc": [""], "params": ["a", "b"]},
            ValueError,
        ),
        (
            {"id": 1, "method": "test.method", "jsonrpc": [], "params": ["a", "b"]},
            ValueError,
        ),
        ({"id": 1, "method": "test.method", "params": ["a", "b"]}, ValueError),
        # test "params" member
        (
            {"id": 1, "method": "test.method", "jsonrpc": "2.0", "params": ["a", "b"]},
            None,
        ),
        ({"id": 1, "method": "test.method", "jsonrpc": "2.0", "params": []}, None),
        ({"id": 1, "method": "test.method", "jsonrpc": "2.0"}, None),
        ({"id": 1, "method": "test.method", "jsonrpc": "2.0", "params": 1}, ValueError),
        (
            {"id": 1, "method": "test.method", "jsonrpc": "2.0", "params": "bad"},
            ValueError,
        ),
        (
            {"id": 1, "method": "test.method", "jsonrpc": "2.0", "params": None},
            ValueError,
        ),
        # fuzzy
        ({}, ValueError),
    ],
)
@pytest.mark.asyncio
async def test_validate_message(ws_msg, error_type):
    if error_type is not None:
        with pytest.raises(error_type):
            await RpcWebSocketHandler.validate_message(ws_msg)
    else:
        await RpcWebSocketHandler.validate_message(ws_msg)
