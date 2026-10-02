import logging
import os
from unittest.mock import Mock

from mako.template import Template
import pytest

import middlewared
from middlewared.api.current import NTPServerEntry
from middlewared.pytest.unit.middleware import Middleware

TEMPLATE = os.path.join(os.path.dirname(middlewared.__file__), "etc_files", "chrony", "chrony.conf.mako")


def render(servers, *, require_nts=False):
    m = Middleware()
    m.services.system.ntpserver.query = Mock(return_value=servers)
    m.services.system.security.config = Mock(return_value=Mock(require_nts=require_nts))
    lines = Template(filename=TEMPLATE).render(middleware=m).splitlines()
    return [line for line in lines if line and not line.startswith("#")]


def server(id_, address, **kwargs):
    return NTPServerEntry(id=id_, address=address, **kwargs)


def test_nts_servers():
    lines = render([server(1, "time.cloudflare.com", nts=True), server(2, "0.debian.pool.ntp.org")])

    assert [line for line in lines if line.startswith("server ")] == [
        "server time.cloudflare.com iburst maxpoll 10 minpoll 6 nts",
        "server 0.debian.pool.ntp.org iburst maxpoll 10 minpoll 6",
    ]


@pytest.mark.parametrize("require_nts,mode", [(False, "prefer"), (True, "require")])
def test_authselectmode(require_nts, mode):
    assert [line for line in render([], require_nts=require_nts) if line.startswith("authselectmode")] == [
        f"authselectmode {mode}"
    ]


@pytest.mark.parametrize("address", ["127.0.0.1\npidfile /etc/passwd", "127.0.0.1 port 1234", "127.0.0.1\t"])
def test_an_address_stored_before_it_was_constrained_is_skipped(caplog, address):
    with caplog.at_level(logging.WARNING):
        lines = render([server(1, address), server(2, "0.debian.pool.ntp.org")])

    assert [line for line in lines if line.startswith("server ")] == [
        "server 0.debian.pool.ntp.org iburst maxpoll 10 minpoll 6"
    ]
    assert not any(line.startswith("pidfile") for line in lines)
    assert "address must be a single word" in caplog.text
