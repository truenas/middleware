import pytest

from middlewared.utils.dns import build_nsupdate_payload, nsupdate_directive


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
    ],
)
def test_nsupdate_directive(command, name, ttl, rtype, rdata, expected):
    # The API accepts upper-case ADD / DELETE; nsupdate expects lower case.
    assert nsupdate_directive(command, name, ttl, rtype, rdata) == expected


# ---- build_nsupdate_payload ---------------------------------------------------


def test_full_payload_forward_grouped_each_ptr_own_send():
    # The reported bug: IPv4 (in-addr.arpa) and IPv6 (ip6.arpa) PTRs must not
    # share a transaction. Forward A/AAAA go together; each PTR gets its own send.
    payload = build_nsupdate_payload(
        [_op("192.168.1.5", "A"), _op("2001:db8::5", "AAAA")]
    )
    assert payload == (
        "update add truenas.ad.example.com. 3600 A 192.168.1.5 \n"
        "update add truenas.ad.example.com. 3600 AAAA 2001:db8::5 \n"
        "send\n"
        "update add 5.1.168.192.in-addr.arpa 3600 PTR truenas.ad.example.com. \n"
        "send\n"
        f"update add {IPV6_PTR} 3600 PTR truenas.ad.example.com. \n"
        "send\n"
    )


def test_no_ptr_single_send():
    payload = build_nsupdate_payload([_op("192.168.1.5", "A", do_ptr=False)])
    assert payload == "update add truenas.ad.example.com. 3600 A 192.168.1.5 \nsend\n"
    assert payload.count("send\n") == 1


def test_send_count_is_one_forward_plus_one_per_ptr():
    payload = build_nsupdate_payload(
        [_op("192.168.1.5", "A"), _op("2001:db8::5", "AAAA")]
    )
    assert payload.count("send\n") == 3  # forward + 2 PTRs


def test_ipv4_and_ipv6_ptrs_never_share_a_transaction():
    payload = build_nsupdate_payload(
        [_op("192.168.1.5", "A"), _op("2001:db8::5", "AAAA")]
    )
    # Split into transactions by "send"; no single transaction holds both families.
    transactions = payload.split("send\n")
    for txn in transactions:
        assert not ("in-addr.arpa" in txn and "ip6.arpa" in txn)


def test_do_ptr_false_excludes_reverse():
    payload = build_nsupdate_payload(
        [
            _op("192.168.1.5", "A", do_ptr=True),
            _op("2001:db8::5", "AAAA", do_ptr=False),
        ]
    )
    assert "5.1.168.192.in-addr.arpa" in payload
    assert "ip6.arpa" not in payload
    assert payload.count("send\n") == 2  # forward + the single IPv4 PTR


def test_ptr_uses_its_own_op_command_and_ttl():
    # Regression: each PTR must use the command/ttl of the op that produced it,
    # not a value carried over from another op in the list.
    payload = build_nsupdate_payload(
        [
            _op("192.168.1.5", "A", command="ADD", ttl=3600),
            _op("192.168.1.6", "A", command="DELETE", ttl=60),
        ]
    )
    assert (
        "update add 5.1.168.192.in-addr.arpa 3600 PTR truenas.ad.example.com. \n"
        in payload
    )
    assert (
        "update delete 6.1.168.192.in-addr.arpa 60 PTR truenas.ad.example.com. \n"
        in payload
    )
