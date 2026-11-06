import pytest

from middlewared.plugins.ntp.enums import ChronyAuthMode, ChronyReply, ChronyRequest
from middlewared.plugins.ntp.peers import (
    AUTH_DATA,
    N_SOURCES,
    NEVER,
    REPLY_HEADER,
    REQUEST_HEADER,
    SOURCE_DATA,
    SOURCE_NAME,
    chronyd_nts_sources,
    chronyd_request,
    parse_auth_data,
    parse_source_data,
    parse_source_name,
)
from middlewared.service_exception import CallError

# SOURCE_DATA reply payloads captured from chronyd 4.6.1, expected values are what `chronyc -c sources` printed for them
BEST = "9e33631300000000000000000000000000010000000a000200000000000000ff000002abef5020dded162545f88bf120"
SELECTABLE = "a6588e3400000000000000000000000000010000000a000200050000000000ff0000037cf2fd793df485ff69fad3177d"


@pytest.mark.parametrize(
    "data,expected",
    [
        (
            BEST,
            {
                "mode": "SERVER",
                "state": "BEST",
                "remote": "158.51.99.19",
                "stratum": 2,
                "poll_interval": 10,
                "reach": 0o377,
                "lastrx": 683,
                "offset": -0.000446042,
                "offset_measured": -0.000670897,
                "jitter": 0.017082751,
                "active": True,
            },
        ),
        (
            SELECTABLE,
            {
                "mode": "SERVER",
                "state": "SELECTABLE",
                "remote": "166.88.142.52",
                "stratum": 2,
                "poll_interval": 10,
                "reach": 0o377,
                "lastrx": 892,
                "offset": 0.004089285,
                "offset_measured": 0.003867700,
                "jitter": 0.051536072,
                "active": False,
            },
        ),
    ],
)
def test_parse_source_data(data, expected):
    assert parse_source_data(bytes.fromhex(data)) == pytest.approx(expected)


def test_parse_source_data_unresolved():
    # Address family IPADDR_ID
    assert parse_source_data(bytes.fromhex(BEST[:32] + "0003" + BEST[36:])) is None


class FakeSocket:
    def __init__(self, reply):
        self.reply = reply

    def send(self, data):
        self.sent = data

    def recv(self, size):
        return self.reply


def source_data_request(sock):
    return chronyd_request(
        sock, 1, ChronyRequest.SOURCE_DATA, N_SOURCES.pack(0), ChronyReply.SOURCE_DATA, SOURCE_DATA.size
    )


def reply(
    version=6, pkt_type=2, reserved=0, command=ChronyRequest.SOURCE_DATA, code=ChronyReply.SOURCE_DATA, status=0, seq=1
):
    return REPLY_HEADER.pack(version, pkt_type, reserved, 0, command, code, status, 0, 0, 0, seq, 0, 0) + bytes.fromhex(
        BEST
    )


def test_chronyd_request():
    sock = FakeSocket(reply())
    assert source_data_request(sock) == bytes.fromhex(BEST)
    # Same bytes as libchrony sends for this request, padded to the length of the reply
    assert sock.sent.hex() == "06010000000f00000000000100000000000000000000000000000000".ljust(152, "0")


@pytest.mark.parametrize(
    "bad_reply",
    [
        reply(version=5),
        reply(pkt_type=1),
        reply(reserved=1),
        reply(command=ChronyRequest.SOURCE_DATA - 1),
        reply(code=ChronyReply.SOURCE_DATA + 1),
        reply(status=4),
        reply(seq=2),
        reply()[:-1],
        reply()[:20],
        b"",
    ],
)
def test_chronyd_request_bad_reply(bad_reply):
    with pytest.raises(CallError):
        source_data_request(FakeSocket(bad_reply))


AUTH_NTS = AUTH_DATA.pack(ChronyAuthMode.NTS, 15, 1, 256, 0, 120, 8, 100, 0, 0)
AUTH_NONE = AUTH_DATA.pack(ChronyAuthMode.NONE, 0, 0, 0, 0, 0, 0, 0, 0, 0)


@pytest.mark.parametrize(
    "data,expected",
    [
        (AUTH_NTS, {"name": "nts.example.net", "key_length": 256, "cookies": 8, "attempts": 0, "last_success": 120}),
        (
            AUTH_DATA.pack(ChronyAuthMode.NTS, 0, 0, 0, 3, NEVER, 0, 0, 0, 0),
            {"name": "nts.example.net", "key_length": 0, "cookies": 0, "attempts": 3, "last_success": None},
        ),
    ],
)
def test_parse_auth_data(data, expected):
    assert parse_auth_data("nts.example.net", data) == expected


@pytest.mark.parametrize(
    "name,expected",
    [
        (b"time.cloudflare.com", "time.cloudflare.com"),
        (b"192.0.2.1", "192.0.2.1"),
        # chronyc prints these as ?
        (b"", "?"),
        (b"x" * 256, "?"),
        (b"bad name", "?"),
        (b"bad\nname", "?"),
    ],
)
def test_parse_source_name(name, expected):
    assert parse_source_name(SOURCE_NAME.pack(name)) == expected


class FakeChronyd:
    """Answer requests from canned payloads, keyed by the address the request carries, as chronyd would"""

    def __init__(self, sources, auth, names):
        self.sources = sources
        self.auth = auth
        self.names = names
        self.requests = []

    def send(self, data):
        _, _, _, _, command, _, seq, _, _ = REQUEST_HEADER.unpack_from(data)
        header_size = REQUEST_HEADER.size
        body = data[header_size:]
        self.requests.append((ChronyRequest(command), len(data)))
        match command:
            case ChronyRequest.N_SOURCES:
                code, payload = ChronyReply.N_SOURCES, N_SOURCES.pack(len(self.sources))
            case ChronyRequest.SOURCE_DATA:
                code, payload = ChronyReply.SOURCE_DATA, self.sources[N_SOURCES.unpack_from(body)[0]]
            case ChronyRequest.AUTH_DATA:
                code, payload = ChronyReply.AUTH_DATA, self.auth[body[:20]]
            case ChronyRequest.NTP_SOURCE_NAME:
                code, payload = ChronyReply.NTP_SOURCE_NAME, SOURCE_NAME.pack(self.names[body[:20]])
        self.reply = REPLY_HEADER.pack(6, 2, 0, 0, command, code, 0, 0, 0, 0, seq, 0, 0) + payload

    def recv(self, size):
        return self.reply


def test_chronyd_nts_sources():
    nts = bytes.fromhex(BEST)
    plain = bytes.fromhex(SELECTABLE)
    # Reference clock (RPY_SD_MD_REF), and an NTS server whose name has not resolved yet (IPADDR_ID)
    refclock = b"GPS\0" + plain[4:26] + b"\x00\x02" + plain[28:]
    unresolved = (7).to_bytes(4, "big") + bytes(12) + b"\x00\x03" + plain[18:]
    chronyd = FakeChronyd(
        [nts, plain, refclock, unresolved],
        {nts[:20]: AUTH_NTS, plain[:20]: AUTH_NONE, unresolved[:20]: AUTH_NTS},
        {nts[:20]: b"time.cloudflare.com", unresolved[:20]: b"nts.example.net"},
    )

    assert [source["name"] for source in chronyd_nts_sources(chronyd)] == ["time.cloudflare.com", "nts.example.net"]
    # Nothing is asked about the reference clock, and only NTS sources are asked for their name. Each request is
    # padded to the length of its reply, which chronyd requires.
    assert chronyd.requests == [
        (ChronyRequest.N_SOURCES, 32),
        (ChronyRequest.SOURCE_DATA, 76),
        (ChronyRequest.SOURCE_DATA, 76),
        (ChronyRequest.SOURCE_DATA, 76),
        (ChronyRequest.SOURCE_DATA, 76),
        (ChronyRequest.AUTH_DATA, 52),
        (ChronyRequest.NTP_SOURCE_NAME, 284),
        (ChronyRequest.AUTH_DATA, 52),
        (ChronyRequest.AUTH_DATA, 52),
        (ChronyRequest.NTP_SOURCE_NAME, 284),
    ]
