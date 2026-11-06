"""`system.ntpserver` validation: which probes run, against what, and where their errors land.

Both probes are monkeypatched, so nothing is sent; the test middleware runs `to_thread` inline.
"""

import logging
from unittest.mock import AsyncMock, Mock

import pytest

from middlewared.api.current import NTPServerEntry, NTPServerUpdate
from middlewared.plugins.ntp.crud import NTPServerServicePart
from middlewared.pytest.unit.middleware import FakeJob, Middleware
from middlewared.service import CallError, ValidationErrors
from middlewared.service.context import ServiceContext
from middlewared.utils.ntp import NTSKEError, NTSKEResult

ADDRESS = "time.example.net"


def entry(**kwargs):
    return NTPServerEntry(**({"id": 1, "address": ADDRESS} | kwargs))


@pytest.fixture
def probes(monkeypatch):
    """Record every probe `validate` runs, and let a test choose their outcomes."""
    calls = []
    outcome = {"nts": NTSKEResult(aead=15, cookies=8, server=None, port=None), "ntp": True}

    def fake_nts_probe(host):
        calls.append(("nts", host))
        if isinstance(outcome["nts"], Exception):
            raise outcome["nts"]
        return outcome["nts"]

    def fake_ntp_probe(host, port=123):
        calls.append(("ntp", host, port))
        return outcome["ntp"]

    monkeypatch.setattr("middlewared.plugins.ntp.crud.probe_nts_ke", fake_nts_probe)
    monkeypatch.setattr("middlewared.plugins.ntp.crud.test_ntp_server", fake_ntp_probe)
    return calls, outcome


def service_part(*, require_nts=False, other_nts_servers=()):
    """A service part whose `system.security` has `require_nts` set as given, and whose only other NTS servers
    (whatever `query` is asked for) are `other_nts_servers`."""
    m = Middleware()
    m.services.system.security.config = Mock(return_value=Mock(require_nts=require_nts))
    m.services.service.control = Mock(return_value=FakeJob())
    svc_part = NTPServerServicePart(ServiceContext(m, logging.getLogger("test")))
    svc_part.query = AsyncMock(return_value=list(other_nts_servers))
    return svc_part


async def errors(data, *, force=False, schema="ntpserver_create", svc_part=None):
    try:
        await (svc_part or service_part()).validate(data, schema, force=force)
    except ValidationErrors as e:
        return {error.attribute: error.errmsg for error in e.errors}

    return {}


@pytest.mark.asyncio
async def test_a_plain_server_is_only_checked_over_ntp(probes):
    calls, _ = probes

    assert await errors(entry()) == {}
    assert calls == [("ntp", ADDRESS, 123)]


@pytest.mark.asyncio
async def test_an_nts_server_is_checked_with_key_establishment_first(probes):
    calls, _ = probes

    assert await errors(entry(nts=True)) == {}
    assert calls == [("nts", ADDRESS), ("ntp", ADDRESS, 123)]


@pytest.mark.asyncio
async def test_the_negotiated_ntp_server_is_the_one_checked(probes):
    calls, outcome = probes
    outcome["nts"] = NTSKEResult(aead=15, cookies=8, server="ntp.example.net", port=1234)

    assert await errors(entry(nts=True)) == {}
    assert calls == [("nts", ADDRESS), ("ntp", "ntp.example.net", 1234)]


@pytest.mark.asyncio
async def test_a_key_establishment_failure_is_reported_on_nts(probes):
    calls, outcome = probes
    outcome["nts"] = NTSKEError("unable to connect to TCP port 4460: Connection refused")

    assert await errors(entry(nts=True)) == {
        "ntpserver_create.nts": (
            f"NTS key establishment with {ADDRESS} failed: unable to connect to TCP port 4460: Connection refused. "
            'Check "Force" to continue regardless.'
        ),
    }
    assert calls == [("nts", ADDRESS)]


@pytest.mark.asyncio
async def test_unreachable_ntp_after_key_establishment_is_reported_on_address(probes):
    _, outcome = probes
    outcome["ntp"] = False

    assert list(await errors(entry(nts=True))) == ["ntpserver_create.address"]


@pytest.mark.asyncio
@pytest.mark.parametrize("nts", [False, True])
async def test_force_skips_the_probes(probes, nts):
    calls, _ = probes

    assert await errors(entry(nts=nts), force=True) == {}
    assert calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("force", [False, True])
async def test_nts_caps_maxpoll_even_when_forced(probes, force):
    """chrony would re-run key establishment on every poll and never exchange NTP packets."""
    assert list(await errors(entry(nts=True, maxpoll=22), force=force)) == ["ntpserver_create.maxpoll"]
    assert await errors(entry(nts=True, maxpoll=21), force=force) == {}
    assert await errors(entry(maxpoll=22), force=force) == {}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "require_nts,nts,force,expected",
    [
        (True, False, False, ["ntpserver_update.nts"]),
        (True, False, True, ["ntpserver_update.nts"]),
        (True, True, False, []),
        (False, False, False, []),
    ],
)
async def test_servers_without_nts_are_refused_while_nts_is_required(probes, require_nts, nts, force, expected):
    """chronyd would never use one, so it is refused, whether it is new or has NTS turned off, before any probe."""
    calls, _ = probes
    svc_part = service_part(require_nts=require_nts)

    assert list(await errors(entry(nts=nts), force=force, schema="ntpserver_update", svc_part=svc_part)) == expected
    if expected:
        assert calls == []


@pytest.mark.asyncio
async def test_the_last_nts_server_cannot_be_deleted_while_required():
    svc_part = service_part(require_nts=True)
    svc_part.get_instance = AsyncMock(return_value=entry(nts=True))
    svc_part._delete = AsyncMock()

    audit_callback = Mock()

    with pytest.raises(CallError, match="The last NTS server cannot be deleted"):
        await svc_part.do_delete(audit_callback, 1)
    svc_part._delete.assert_not_called()
    # Audited even though it was refused
    audit_callback.assert_called_once_with(ADDRESS)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "require_nts,nts,other_nts_servers",
    [
        (True, True, [entry(id=2, nts=True)]),
        (True, False, []),
        (False, True, []),
    ],
)
async def test_other_deletes_go_ahead(require_nts, nts, other_nts_servers):
    svc_part = service_part(require_nts=require_nts, other_nts_servers=other_nts_servers)
    svc_part.get_instance = AsyncMock(return_value=entry(nts=nts))
    svc_part._delete = AsyncMock()

    audit_callback = Mock()

    await svc_part.do_delete(audit_callback, 1)
    svc_part._delete.assert_awaited_once_with(1)
    audit_callback.assert_called_once_with(ADDRESS)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "require_nts,nts_servers,expected",
    [
        (False, [], ""),
        (False, [entry(id=1, address="time.example.net", nts=True)], "NTS servers (time.example.net)"),
        (True, [entry(id=1, address="time.example.net", nts=True)], "NTS is required"),
    ],
)
async def test_domain_clock_advice(require_nts, nts_servers, expected):
    svc_part = service_part(require_nts=require_nts, other_nts_servers=nts_servers)

    advice = await svc_part.domain_clock_advice()

    if expected:
        assert expected in advice
    else:
        assert advice == ""
    svc_part.query.assert_awaited_once_with([["nts", "=", True]])


@pytest.mark.asyncio
async def test_update_is_audited_by_the_address_it_had(probes):
    """A change of address is audited by the server it was made to, the new address is in the parameters."""
    svc_part = service_part()
    svc_part.get_instance = AsyncMock(return_value=entry())
    svc_part._update = AsyncMock(return_value=entry(address="ntp.example.net"))
    audit_callback = Mock()

    await svc_part.do_update(audit_callback, 1, NTPServerUpdate(address="ntp.example.net"))
    audit_callback.assert_called_once_with(ADDRESS)
