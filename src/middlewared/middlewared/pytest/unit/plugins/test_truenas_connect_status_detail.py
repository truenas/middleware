from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from truenas_connect_utils.status import Status

from middlewared.plugins.truenas_connect import finalize_registration as finalize
from middlewared.plugins.truenas_connect.config import TrueNASConnectConfigServicePart
from middlewared.plugins.truenas_connect.internal import set_status
from middlewared.plugins.truenas_connect.utils import CLAIM_TOKEN_CACHE_KEY, get_unset_payload

GENERIC_REASON = Status.REGISTRATION_FINALIZATION_FAILED.value


@pytest.fixture
def context() -> MagicMock:
    config = MagicMock(id=1, status=Status.REGISTRATION_FINALIZATION_WAITING.name)
    ctx = MagicMock()
    ctx.call2 = AsyncMock(return_value=config)
    ctx.middleware.call = AsyncMock(return_value="claim-token")
    return ctx


def datastore_updates(context: MagicMock) -> list[dict[str, Any]]:
    return [
        call.args[3]
        for call in context.middleware.call.await_args_list
        if call.args[:2] == ("datastore.update", "truenas_connect")
    ]


async def run_finalize(context: MagicMock, poll_response: dict[str, Any]) -> None:
    with (
        patch.object(finalize, "config_internal", AsyncMock(return_value={})),
        patch.object(finalize, "_poll_once", AsyncMock(return_value=poll_response)),
    ):
        await finalize.finalize_registration_impl(context)


async def extend(**row: Any) -> dict[str, Any]:
    row = {"certificate": None, "registration_details": {}, "status_detail": None} | row
    return await TrueNASConnectConfigServicePart.extend(MagicMock(), row)


@pytest.mark.asyncio
async def test_extend_reports_stored_detail_as_status_reason_and_hides_the_column():
    data = await extend(status=Status.REGISTRATION_FINALIZATION_FAILED.name, status_detail="Some reason")

    assert data["status_reason"] == "Some reason"
    assert "status_detail" not in data


@pytest.mark.asyncio
async def test_extend_falls_back_to_generic_status_text():
    data = await extend(status=Status.REGISTRATION_FINALIZATION_FAILED.name)

    assert data["status_reason"] == GENERIC_REASON
    assert "status_detail" not in data


@pytest.mark.asyncio
async def test_set_status_clears_detail_by_default(context: MagicMock):
    await set_status(context, Status.REGISTRATION_FINALIZATION_WAITING.name)

    assert datastore_updates(context) == [
        {"status": Status.REGISTRATION_FINALIZATION_WAITING.name, "status_detail": None},
    ]


def test_unset_payload_clears_detail():
    assert get_unset_payload()["status_detail"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response,status_code,detail",
    [
        ({"error": "limit exceeded"}, 400, "The TrueNAS Connect account has reached its system limit"),
        ({"error": "invalid claim token"}, 400, "TrueNAS Connect rejected the claim token"),
        ({"error": "system revoked"}, 403, "TrueNAS Connect rejected the registration: system revoked"),
        ({"unexpected": "body"}, 403, None),
        ("Forbidden", 403, None),
        ({}, 200, None),
    ],
)
async def test_terminal_response_stores_the_reason(
    context: MagicMock,
    response: Any,
    status_code: int,
    detail: str | None,
):
    await run_finalize(context, {"status_code": status_code, "response": response, "error": None})

    assert datastore_updates(context) == [
        {"status": Status.REGISTRATION_FINALIZATION_FAILED.name, "status_detail": detail},
    ]


@pytest.mark.asyncio
async def test_invalid_token_in_successful_response_keeps_generic_text(context: MagicMock):
    with patch.object(finalize, "decode_and_validate_token", side_effect=ValueError("bad token")):
        await run_finalize(context, {"status_code": 200, "response": {"token": "bad"}, "error": None})

    assert datastore_updates(context) == [
        {"status": Status.REGISTRATION_FINALIZATION_FAILED.name, "status_detail": None},
    ]


@pytest.mark.asyncio
async def test_expired_claim_token_has_no_detail(context: MagicMock):
    async def call(method: str, *args: Any) -> None:
        if method == "cache.get":
            assert args == (CLAIM_TOKEN_CACHE_KEY,)
            raise KeyError(args[0])

    context.middleware.call = AsyncMock(side_effect=call)

    await finalize.finalize_registration_impl(context)

    assert datastore_updates(context) == [
        {"status": Status.REGISTRATION_FINALIZATION_TIMEOUT.name, "status_detail": None},
    ]


@pytest.mark.asyncio
async def test_pending_registration_keeps_polling_without_changing_status(context: MagicMock):
    waiting, stopped = context.call2.return_value, MagicMock(status=Status.DISABLED.name)
    context.call2 = AsyncMock(side_effect=[waiting, stopped])

    with patch.object(finalize.asyncio, "sleep", AsyncMock()):
        await run_finalize(context, {"status_code": 400, "response": {"error": "not found"}, "error": None})

    assert datastore_updates(context) == []
