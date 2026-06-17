from unittest.mock import Mock

import pytest
from truenas_pylibvirt.libvirtd.connection import DomainState

from middlewared.pylibvirt import gather_pylibvirt_domains_states


class DomainGone(Exception):
    """An error that is_no_domain_error() classifies as a vanished domain."""


@pytest.fixture
def classify_domain_gone(monkeypatch):
    # Patch the classifier rather than constructing real libvirt errors in the test.
    monkeypatch.setattr(
        "middlewared.pylibvirt.is_no_domain_error",
        lambda exc: isinstance(exc, DomainGone),
    )


class FakeDomain:
    """Stands in for a libvirt domain object returned by listAllDomains()."""

    def __init__(self, name, domain_state=DomainState.RUNNING, active=True, raises=None, name_raises=None):
        self._name = name
        self._domain_state = domain_state
        self._active = active
        self._raises = raises
        self._name_raises = name_raises

    def name(self):
        if self._name_raises is not None:
            raise self._name_raises
        return self._name

    def domain_state(self):
        if self._raises is not None:
            raise self._raises
        return self._domain_state

    def isActive(self):
        return self._active


class FakeConnection:
    def __init__(self, domains):
        self._domains = domains

    def list_domains(self):
        return list(self._domains)

    def domain_state(self, domain):
        return domain.domain_state()


class DummyDomain:
    """Stands in for the BaseDomain built by container_factory; pid() reads a pidfile."""

    def pid(self):
        return None


def make_middleware(system_state="READY"):
    middleware = Mock()
    middleware.call_sync.return_value = system_state
    middleware.logger = Mock()
    return middleware


def factory(_row):
    return DummyDomain()


def test_vanished_domain_does_not_poison_the_batch(classify_domain_gone):
    middleware = make_middleware()
    domains = [
        FakeDomain("uuid-gone", raises=DomainGone()),
        FakeDomain("uuid-1"),
        FakeDomain("uuid-2"),
        FakeDomain("uuid-3"),
    ]
    rows = [{"uuid": "uuid-gone"}, {"uuid": "uuid-1"}, {"uuid": "uuid-2"}, {"uuid": "uuid-3"}]

    state = gather_pylibvirt_domains_states(middleware, rows, FakeConnection(domains), factory)

    assert set(state) == {"uuid-1", "uuid-2", "uuid-3"}
    assert "uuid-gone" not in state
    assert state["uuid-1"] == {"state": "RUNNING", "pid": None, "domain_state": "RUNNING"}
    middleware.logger.debug.assert_called_once()
    middleware.logger.error.assert_not_called()


def test_genuine_error_is_logged_and_isolated(classify_domain_gone):
    middleware = make_middleware()
    domains = [FakeDomain("uuid-bad"), FakeDomain("uuid-ok")]
    rows = [{"uuid": "uuid-bad"}, {"uuid": "uuid-ok"}]

    def boom_factory(row):
        if row["uuid"] == "uuid-bad":
            raise KeyError("idmap")
        return DummyDomain()

    state = gather_pylibvirt_domains_states(middleware, rows, FakeConnection(domains), boom_factory)

    assert set(state) == {"uuid-ok"}
    middleware.logger.error.assert_called_once()
    assert middleware.logger.error.call_args.kwargs.get("exc_info") is True
    middleware.logger.debug.assert_not_called()


def test_list_domains_failure_returns_empty_without_raising():
    middleware = make_middleware()
    connection = Mock()
    connection.list_domains.side_effect = RuntimeError("libvirt is down")
    rows = [{"uuid": "uuid-1"}, {"uuid": "uuid-2"}]

    # A connection-level libvirt failure must never propagate out of the call.
    state = gather_pylibvirt_domains_states(middleware, rows, connection, factory)

    assert state == {}
    middleware.logger.warning.assert_called_once()
    assert middleware.logger.warning.call_args.kwargs.get("exc_info") is True


def test_domain_name_failure_is_isolated(classify_domain_gone):
    middleware = make_middleware()
    domains = [FakeDomain("uuid-bad", name_raises=DomainGone()), FakeDomain("uuid-ok")]
    rows = [{"uuid": "uuid-ok"}]

    state = gather_pylibvirt_domains_states(middleware, rows, FakeConnection(domains), factory)

    assert set(state) == {"uuid-ok"}
    # name() raising a no-domain error is classified as the vanished-domain race -> DEBUG, not ERROR.
    middleware.logger.error.assert_not_called()


def test_no_rows_skips_libvirt_entirely():
    middleware = make_middleware()
    connection = Mock()

    assert gather_pylibvirt_domains_states(middleware, [], connection, factory) == {}
    middleware.call_sync.assert_not_called()
    connection.list_domains.assert_not_called()


def test_shutting_down_returns_empty():
    middleware = make_middleware(system_state="SHUTTING_DOWN")
    connection = Mock()
    rows = [{"uuid": "uuid-1"}]

    assert gather_pylibvirt_domains_states(middleware, rows, connection, factory) == {}
    connection.list_domains.assert_not_called()


def test_non_queried_vanished_domain_is_ignored():
    middleware = make_middleware()
    # A domain that is NOT in rows would raise while reading state; it must never be touched.
    domains = [FakeDomain("uuid-not-queried", raises=DomainGone()), FakeDomain("uuid-1")]
    rows = [{"uuid": "uuid-1"}]

    state = gather_pylibvirt_domains_states(middleware, rows, FakeConnection(domains), factory)

    assert set(state) == {"uuid-1"}
    middleware.logger.debug.assert_not_called()
    middleware.logger.error.assert_not_called()


@pytest.mark.parametrize(
    "domain_state,active,expected",
    [
        (DomainState.RUNNING, True, "RUNNING"),
        (DomainState.PAUSED, True, "SUSPENDED"),
        (DomainState.SHUTOFF, False, "STOPPED"),
    ],
)
def test_state_mapping(domain_state, active, expected):
    middleware = make_middleware()
    domains = [FakeDomain("uuid-1", domain_state=domain_state, active=active)]
    rows = [{"uuid": "uuid-1"}]

    state = gather_pylibvirt_domains_states(middleware, rows, FakeConnection(domains), factory)

    assert state["uuid-1"]["state"] == expected
