from unittest.mock import Mock

import libvirt
import pytest

from middlewared.pylibvirt import gather_pylibvirt_domains_states


def no_domain_error():
    e = libvirt.libvirtError("virDomainGetState() failed")
    e.err = (libvirt.VIR_ERR_NO_DOMAIN, None, "Domain not found", None, None, None, None, -1, -1)
    return e


class FakeDomain:
    """Stands in for a libvirt domain object returned by listAllDomains()."""

    def __init__(self, name, state=libvirt.VIR_DOMAIN_RUNNING, raises=None):
        self._name = name
        self._state = state
        self._raises = raises

    def name(self):
        return self._name

    def state(self):
        if self._raises is not None:
            raise self._raises
        return (self._state, 0)

    def isActive(self):
        return self._state in (libvirt.VIR_DOMAIN_RUNNING, libvirt.VIR_DOMAIN_PAUSED)


class FakeConnection:
    def __init__(self, domains):
        self._domains = domains

    def list_domains(self):
        return list(self._domains)

    def domain_state(self, domain):
        # Mirror truenas_pylibvirt.Connection.domain_state: a live call into the domain.
        from truenas_pylibvirt.libvirtd.connection import DomainState

        return {
            libvirt.VIR_DOMAIN_RUNNING: DomainState.RUNNING,
            libvirt.VIR_DOMAIN_PAUSED: DomainState.PAUSED,
            libvirt.VIR_DOMAIN_SHUTOFF: DomainState.SHUTOFF,
        }[domain.state()[0]]


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


def test_vanished_domain_does_not_poison_the_batch():
    middleware = make_middleware()
    domains = [
        FakeDomain("uuid-gone", raises=no_domain_error()),
        FakeDomain("uuid-1"),
        FakeDomain("uuid-2"),
        FakeDomain("uuid-3"),
    ]
    rows = [{"uuid": d.name()} for d in domains]

    state = gather_pylibvirt_domains_states(middleware, rows, FakeConnection(domains), factory)

    assert set(state) == {"uuid-1", "uuid-2", "uuid-3"}
    assert "uuid-gone" not in state
    assert state["uuid-1"] == {"state": "RUNNING", "pid": None, "domain_state": "RUNNING"}
    middleware.logger.debug.assert_called_once()
    middleware.logger.error.assert_not_called()


def test_genuine_error_is_logged_and_isolated():
    middleware = make_middleware()
    domains = [FakeDomain("uuid-bad"), FakeDomain("uuid-ok")]
    rows = [{"uuid": d.name()} for d in domains]

    def boom_factory(row):
        if row["uuid"] == "uuid-bad":
            raise KeyError("idmap")
        return DummyDomain()

    state = gather_pylibvirt_domains_states(middleware, rows, FakeConnection(domains), boom_factory)

    assert set(state) == {"uuid-ok"}
    middleware.logger.error.assert_called_once()
    assert middleware.logger.error.call_args.kwargs.get("exc_info") is True
    middleware.logger.debug.assert_not_called()


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
    # A domain that is NOT in rows raises on state(); it must never be touched.
    domains = [FakeDomain("uuid-not-queried", raises=no_domain_error()), FakeDomain("uuid-1")]
    rows = [{"uuid": "uuid-1"}]

    state = gather_pylibvirt_domains_states(middleware, rows, FakeConnection(domains), factory)

    assert set(state) == {"uuid-1"}
    middleware.logger.debug.assert_not_called()
    middleware.logger.error.assert_not_called()


@pytest.mark.parametrize(
    "vir_state,expected",
    [
        (libvirt.VIR_DOMAIN_RUNNING, "RUNNING"),
        (libvirt.VIR_DOMAIN_PAUSED, "SUSPENDED"),
        (libvirt.VIR_DOMAIN_SHUTOFF, "STOPPED"),
    ],
)
def test_state_mapping(vir_state, expected):
    middleware = make_middleware()
    domains = [FakeDomain("uuid-1", state=vir_state)]
    rows = [{"uuid": "uuid-1"}]

    state = gather_pylibvirt_domains_states(middleware, rows, FakeConnection(domains), factory)

    assert state["uuid-1"]["state"] == expected
