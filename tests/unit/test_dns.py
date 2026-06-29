from types import SimpleNamespace

import pytest

from middlewared.utils.dns import (
    NSUpdateResult,
    build_nsupdate_plan,
    nsupdate_directive,
    run_nsupdate_plan,
)


FQDN = "truenas.ad.example.com."
# ipaddress.reverse_pointer for 2001:db8::5
IPV6_PTR = "5.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.8.b.d.0.1.0.0.2.ip6.arpa"


def _op(address, rtype, command="ADD", ttl=3600, do_ptr=True, name=FQDN):
    return {
        "command": command,
        "name": name,
        "ttl": ttl,
        "type": rtype,
        "address": address,
        "do_ptr": do_ptr,
    }


# ---- nsupdate_directive -------------------------------------------------------


@pytest.mark.parametrize(
    "command,name,ttl,rtype,rdata,expected",
    [
        (
            "ADD",
            FQDN,
            3600,
            "A",
            "192.168.1.5",
            "update add truenas.ad.example.com. 3600 A 192.168.1.5 \n",
        ),
        (
            "DELETE",
            FQDN,
            60,
            "AAAA",
            "2001:db8::5",
            "update delete truenas.ad.example.com. 60 AAAA 2001:db8::5 \n",
        ),
        (
            "ADD",
            "5.1.168.192.in-addr.arpa",
            3600,
            "PTR",
            FQDN,
            "update add 5.1.168.192.in-addr.arpa 3600 PTR truenas.ad.example.com. \n",
        ),
    ],
)
def test_nsupdate_directive(command, name, ttl, rtype, rdata, expected):
    # The API accepts upper-case ADD / DELETE; nsupdate expects lower case.
    assert nsupdate_directive(command, name, ttl, rtype, rdata) == expected


# ---- build_nsupdate_plan: forward --------------------------------------------


def test_forward_records_share_one_transaction():
    # A and AAAA for the same host go into the single forward transaction.
    plan = build_nsupdate_plan([_op("192.168.1.5", "A"), _op("2001:db8::5", "AAAA")])
    assert plan.forward == [
        "update add truenas.ad.example.com. 3600 A 192.168.1.5 \n",
        "update add truenas.ad.example.com. 3600 AAAA 2001:db8::5 \n",
    ]


def test_forward_emitted_even_when_no_ptr():
    plan = build_nsupdate_plan([_op("192.168.1.5", "A", do_ptr=False)])
    assert len(plan.forward) == 1
    assert plan.reverse == []


# ---- build_nsupdate_plan: per-PTR isolation ----------------------------------


def test_ipv4_and_ipv6_ptrs_are_separate_entries():
    # The core fix: the IPv4 (in-addr.arpa) and IPv6 (ip6.arpa) PTRs are distinct
    # reverse entries -> separate transactions -> never share a DNS UPDATE.
    plan = build_nsupdate_plan([_op("192.168.1.5", "A"), _op("2001:db8::5", "AAAA")])
    assert [rp for rp, _ in plan.reverse] == ["5.1.168.192.in-addr.arpa", IPV6_PTR]
    # no single directive ever mixes the two reverse families
    for _, directive in plan.reverse:
        assert not ("in-addr.arpa" in directive and "ip6.arpa" in directive)


def test_multiple_same_family_addresses_each_isolated():
    # Even two IPv4 addresses are isolated -- their reverse zones may be
    # delegated separately, and that is not knowable from the address.
    plan = build_nsupdate_plan([_op("192.168.1.5", "A"), _op("192.168.50.6", "A")])
    assert [rp for rp, _ in plan.reverse] == [
        "5.1.168.192.in-addr.arpa",
        "6.50.168.192.in-addr.arpa",
    ]


def test_do_ptr_false_excludes_reverse():
    plan = build_nsupdate_plan(
        [
            _op("192.168.1.5", "A", do_ptr=True),
            _op("2001:db8::5", "AAAA", do_ptr=False),
        ]
    )
    assert len(plan.forward) == 2
    assert [rp for rp, _ in plan.reverse] == ["5.1.168.192.in-addr.arpa"]


def test_ptr_directive_uses_its_own_op_command_and_ttl():
    # Regression: each PTR directive must use the command/ttl of the op that
    # produced it, not a value carried over from another op in the list.
    plan = build_nsupdate_plan(
        [
            _op("192.168.1.5", "A", command="ADD", ttl=3600),
            _op("192.168.1.6", "A", command="DELETE", ttl=60),
        ]
    )
    assert [d for _, d in plan.reverse] == [
        "update add 5.1.168.192.in-addr.arpa 3600 PTR truenas.ad.example.com. \n",
        "update delete 6.1.168.192.in-addr.arpa 60 PTR truenas.ad.example.com. \n",
    ]


# ---- run_nsupdate_plan: failure accounting -----------------------------------


def _sender(fail_on=None):
    """Fake ``send`` recording its calls. ``fail_on(directives) -> bool`` selects
    which transactions return a non-zero exit code."""
    fail_on = fail_on or (lambda directives: False)
    calls = []

    def send(directives):
        calls.append(list(directives))
        if fail_on(directives):
            return SimpleNamespace(returncode=2, stderr=b"update failed: NOTZONE\n")
        return SimpleNamespace(returncode=0, stderr=b"")

    send.calls = calls
    return send


def _plan():
    return build_nsupdate_plan([_op("192.168.1.5", "A"), _op("2001:db8::5", "AAAA")])


def test_run_all_success():
    plan = _plan()
    send = _sender()
    result = run_nsupdate_plan(plan, send)
    assert result == NSUpdateResult(forward_error=None, ptr_failures=[])
    assert len(send.calls) == 1 + len(plan.reverse)  # forward + one per PTR


def test_run_forward_failure_short_circuits():
    # Forward failure is fatal: its error is captured and the PTRs are NOT
    # attempted, so the AD join's GSSAPI retry sees the forward error promptly.
    plan = _plan()
    send = _sender(fail_on=lambda d: "PTR" not in d[0])
    result = run_nsupdate_plan(plan, send)
    assert result.forward_error == "update failed: NOTZONE\n"
    assert result.ptr_failures == []
    assert len(send.calls) == 1


def test_run_ptr_failure_is_collected_not_fatal():
    # A missing IPv6 reverse zone (NOTZONE) must not fail the operation: forward
    # and the IPv4 PTR still succeed, and only the failing PTR is reported.
    plan = _plan()
    send = _sender(fail_on=lambda d: "ip6.arpa" in d[0])
    result = run_nsupdate_plan(plan, send)
    assert result.forward_error is None
    assert result.ptr_failures == [(IPV6_PTR, "update failed: NOTZONE")]
    assert len(send.calls) == 3  # all transactions attempted


def test_run_collects_every_ptr_failure():
    plan = _plan()
    send = _sender(fail_on=lambda d: "PTR" in d[0])
    result = run_nsupdate_plan(plan, send)
    assert result.forward_error is None
    assert len(result.ptr_failures) == len(plan.reverse) == 2
