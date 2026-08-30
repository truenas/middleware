"""Support ticket routing: the endpoint a ticket goes to is the entitlement's answer.

`new_ticket` and `attach_ticket` make the same decision independently -- one async through
`post`, one sync through `requests` -- so they can drift apart, and each is asserted here.

Network safety is structural rather than incidental. A previous cycle's tests reached the
real support proxy and filed an iX case, so patching `post` is not treated as sufficient:

1. An autouse fixture replaces `post`, `requests` and `sw_version` for every test in this
   module, present and future, without the test having to ask. That deviates from this
   tree's no-fixture convention deliberately -- a test added later must not be able to opt
   out of it by forgetting.
2. A second autouse fixture makes an outbound `connect` raise, catching any path the first
   one did not anticipate.
3. Every assertion is on the URL the stand-in recorded, so a `post` that was silently never
   called fails instead of passing vacuously.
"""

import socket
from unittest.mock import Mock

import pytest
import requests
from truenas_pylicensed.features import LicenseFeature

from middlewared.plugins.support import ADDRESS, SupportService
from middlewared.pytest.unit.entitlements import install_entitlements_for_column
from middlewared.pytest.unit.helpers import create_service
from middlewared.pytest.unit.middleware import FakeJob, Middleware
from middlewared.service import CallError

# SUPPORT's vector (0,0,0,1,0,1) grants on a key and nowhere else, so one granting column
# and one denying one is the whole of the routing decision.
ROUTING_COLUMNS = [("HW+K", True), ("CE+L", False)]

ENTERPRISE_PAYLOAD = {
    "title": "Pool is degraded",
    "body": "One disk faulted overnight.",
    "category": "Hardware",
    "criticality": "Loss of Functionality",
    "environment": "Production",
    "phone": "555-0100",
    "name": "Tester",
    "email": "tester@example.com",
}

COMMUNITY_PAYLOAD = {
    "title": "Pool is degraded",
    "body": "One disk faulted overnight.",
    "token": "a-jira-token",
    "type": "BUG",
}


class _FakeResponse:
    status_code = 200

    def json(self):
        return {"error": None}


class _FakeRequests:
    """Stands in for the `requests` module as support.py sees it.

    `attach_ticket` catches `requests.ConnectionError` and `requests.Timeout`, and an `except`
    clause naming an auto-Mock attribute raises TypeError rather than matching, so the real
    exception classes have to come along.
    """

    ConnectionError = requests.ConnectionError
    Timeout = requests.Timeout

    def __init__(self, urls):
        self._urls = urls

    def post(self, url, **kwargs):
        self._urls.append(url)
        return _FakeResponse()


@pytest.fixture(autouse=True)
def posted_urls(monkeypatch):
    """Record every URL support.py would have posted to, and post to none of them."""
    urls = []

    async def fake_post(url, data, timeout=None):
        urls.append(url)
        return {"error": None, "ticketnum": 42, "message": f"https://{ADDRESS}/ticket/42"}

    monkeypatch.setattr("middlewared.plugins.support.post", fake_post)
    monkeypatch.setattr("middlewared.plugins.support.requests", _FakeRequests(urls))
    monkeypatch.setattr("middlewared.plugins.support.sw_version", lambda: "TrueNAS-26.04.0")
    return urls


@pytest.fixture(autouse=True)
def refuse_outbound_connections(monkeypatch):
    def refuse(self, address):
        raise AssertionError(f"a support unit test tried to connect to {address!r}")

    # Inert under pytest-asyncio: the event loop's self-pipe comes from socketpair(2), which
    # does not go through connect.
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)


def _service(column):
    m = Middleware()
    m["system.vendor.name"] = lambda *args: None
    m["network.general.will_perform_activity"] = lambda *args: None
    m["system.dmidecode_info"] = lambda *args: {"system-serial-number": "TEST-000001"}
    checked = install_entitlements_for_column(m, LicenseFeature.SUPPORT, column)
    # Left as an auto-Mock this is truthy, so data['license_id'] becomes a Mock and json.dumps
    # fails with an error that has nothing to do with what is under test.
    m.services.truenas.license.info_private = lambda: None
    return create_service(m, SupportService), checked


def _payload(entitled):
    return dict(ENTERPRISE_PAYLOAD) if entitled else dict(COMMUNITY_PAYLOAD)


@pytest.mark.asyncio
@pytest.mark.parametrize("column,entitled", ROUTING_COLUMNS)
async def test_new_ticket_routes_to_the_endpoint_its_entitlement_names(posted_urls, column, entitled):
    service, checked = _service(column)

    await service.new_ticket(FakeJob(), _payload(entitled))

    assert checked == [LicenseFeature.SUPPORT]
    expected = "truenas" if entitled else "freenas"
    assert posted_urls == [f"https://{ADDRESS}/{expected}/api/v1.0/ticket"]


@pytest.mark.asyncio
@pytest.mark.parametrize("column,entitled", ROUTING_COLUMNS)
async def test_new_ticket_required_attrs_follow_the_route(posted_urls, column, entitled):
    # The two payload shapes are a union with extra='forbid', so neither is a superset of the
    # other and the wrong one for the chosen route is rejected outright. That rejection is
    # `required_attrs`, and it happens before anything is sent.
    service, _ = _service(column)

    with pytest.raises(CallError) as exc:
        await service.new_ticket(FakeJob(), _payload(not entitled))

    # Named explicitly so the test cannot pass on some unrelated failure that also raises.
    assert "is required" in str(exc.value)
    assert posted_urls == []


@pytest.mark.parametrize("column,entitled", ROUTING_COLUMNS)
def test_attach_ticket_routes_to_the_endpoint_its_entitlement_names(posted_urls, column, entitled):
    # The sync twin of the routing test. It reaches the same decision through call_sync2 and
    # `requests`, so a change to one path is not evidence about the other.
    service, checked = _service(column)

    # A plain Mock rather than FakeJob: this path only ever reads job.pipes.input.r, which it
    # hands straight to the stand-in.
    service.attach_ticket(Mock(), {"ticket": 42, "filename": "debug.txz"})

    assert checked == [LicenseFeature.SUPPORT]
    expected = "truenas" if entitled else "freenas"
    assert posted_urls == [f"https://{ADDRESS}/{expected}/api/v1.0/ticket/attachment"]
