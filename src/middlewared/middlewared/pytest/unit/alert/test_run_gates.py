"""The gates between "this source applies here" and "this source runs this tick".

Applicability is one question and these are another. A source's rule says which systems it is
meaningful on; these two flags say when, on such a system, its answer is worth having. Keeping
them apart is the point -- the flag now called ``post_failover_blackout`` used to carry an HA
licence check as well, which put a licensing predicate in front of a hardware question and hid
enclosure faults on every iX appliance that was not licensed for HA.
"""

import time

import pytest

from middlewared.alert.applicability import declaration_rule_name
from middlewared.plugins.alert import (
    FAILOVER_ALERTS_BACKOFF_SECS,
    AlertFailoverInfo,
    AlertService,
    source_run_gates_pass,
)
from middlewared.pytest.unit.alert.test_applicability_matrix import declarations

# Reached through the mangled names so the production methods are exercised as written, against a
# stub rather than a live service. Both are ordinary coroutine functions; `@private` only tags them.
get_failover_info = AlertService._AlertService__get_failover_info
block_failover_alerts = AlertService.block_failover_alerts


def make_source(*, post_failover_blackout=False, require_stable_peer=False):
    return type(
        "StubAlertSource",
        (),
        {"post_failover_blackout": post_failover_blackout, "require_stable_peer": require_stable_peer},
    )


def make_failover_info(*, past_failover_blackout, run_on_backup_node):
    return AlertFailoverInfo(
        this_node="A",
        other_node="B",
        run_on_backup_node=run_on_backup_node,
        past_failover_blackout=past_failover_blackout,
    )


# post_failover_blackout, require_stable_peer, past_failover_blackout, run_on_backup_node, runs
GATE_TABLE = [
    (False, False, False, False, True),
    (False, False, False, True, True),
    (False, False, True, False, True),
    (False, False, True, True, True),
    (False, True, False, False, False),
    (False, True, False, True, True),
    (False, True, True, False, False),
    (False, True, True, True, True),
    (True, False, False, False, False),
    (True, False, False, True, False),
    (True, False, True, False, True),
    (True, False, True, True, True),
    (True, True, False, False, False),
    (True, True, False, True, False),
    (True, True, True, False, False),
    (True, True, True, True, True),
]


@pytest.mark.parametrize("blackout_flag,peer_flag,past_blackout,stable_peer,runs", GATE_TABLE)
def test_source_run_gates_pass(blackout_flag, peer_flag, past_blackout, stable_peer, runs):
    """Each flag is an independent veto: a source runs only where neither one objects."""
    source = make_source(post_failover_blackout=blackout_flag, require_stable_peer=peer_flag)
    fi = make_failover_info(past_failover_blackout=past_blackout, run_on_backup_node=stable_peer)

    assert source_run_gates_pass(source, fi) is runs


class StubMiddleware:
    """Answers the one question `__get_failover_info` asks before it reaches the peer."""

    def __init__(self, licensed_for_failover):
        self.licensed_for_failover = licensed_for_failover

    async def call(self, method, *args, **kwargs):
        assert method == "failover.licensed", f"unexpected call {method!r} for an unlicensed system"
        return self.licensed_for_failover


class StubAlertService:
    def __init__(self):
        self.middleware = StubMiddleware(False)
        self.blocked_failover_alerts_until = 0


@pytest.mark.asyncio
async def test_blackout_is_open_on_a_system_that_never_failed_over():
    """The blackout window is a time window and nothing else.

    An unlicensed system is past it from boot, so a source carrying `post_failover_blackout` is
    still ran there. This assertion is deliberate: the flag used to be paired with a
    `failover.licensed` check, and restoring that conjunct would silence `EnclosureStatus` on
    every iX appliance without an ENTERPRISE_HA licence again.
    """
    service = StubAlertService()

    assert (await get_failover_info(service)).past_failover_blackout is True


@pytest.mark.asyncio
async def test_the_blackout_closes_for_the_backoff_and_then_reopens(monkeypatch):
    now = 1000.0
    monkeypatch.setattr(time, "monotonic", lambda: now)

    service = StubAlertService()
    assert (await get_failover_info(service)).past_failover_blackout is True

    await block_failover_alerts(service)
    assert (await get_failover_info(service)).past_failover_blackout is False

    now += FAILOVER_ALERTS_BACKOFF_SECS
    assert (await get_failover_info(service)).past_failover_blackout is False

    now += 1
    assert (await get_failover_info(service)).past_failover_blackout is True


# Every source carrying either flag, with the population its own rule admits. Frozen because the
# interesting fact is the odd row out: EnclosureStatus is the only carrier that is not gated on an
# HA licence, which is exactly why dropping the licence conjunct out of the blackout flag changed
# its behaviour and nothing else's. A new carrier, or an existing one changing population, has to
# be written down here and read in review.
CARRIERS = """
EnclosureStatus                  post_failover_blackout   TRUENAS_HARDWARE
Failover                         post_failover_blackout   HA_LICENSED
FailoverCritical                 post_failover_blackout   HA_LICENSED
FailoverDisks                    post_failover_blackout   HA_LICENSED
FailoverDisks                    require_stable_peer      HA_LICENSED
FailoverNetworkCards             post_failover_blackout   HA_LICENSED
FailoverNetworkCards             require_stable_peer      HA_LICENSED
FailoverRemoteSystemInaccessible post_failover_blackout   HA_LICENSED
"""


def test_the_flag_carriers_are_what_was_reviewed():
    live = sorted(
        (name, flag, declaration_rule_name(source))
        for name, kind, source in declarations()
        if kind == "source"
        for flag in ("post_failover_blackout", "require_stable_peer")
        if getattr(source, flag)
    )

    assert live == sorted(tuple(line.split()) for line in CARRIERS.strip().splitlines())
