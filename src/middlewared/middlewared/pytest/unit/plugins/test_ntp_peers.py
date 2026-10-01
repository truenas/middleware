import pytest

from middlewared.plugins.ntp.enums import ChronyReply, ChronyRequest
from middlewared.plugins.ntp.peers import N_SOURCES, REPLY_HEADER, SOURCE_DATA, chronyd_request, parse_source_data
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
