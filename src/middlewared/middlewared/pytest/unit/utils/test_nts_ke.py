import re
import socket
import ssl
import threading

import pytest

from middlewared.utils.ntp import (
    NTSKEClient,
    NTSKEError,
    NTSKEResult,
    RecordType,
    build_request,
    certificate_error,
    encode_record,
    interpret_response,
    parse_records,
    split_records,
)

NEXT_PROTOCOL_NTPV4 = encode_record(RecordType.NEXT_PROTOCOL, b"\x00\x00")
AEAD_AES_SIV_CMAC_256 = encode_record(RecordType.AEAD_ALGORITHM, b"\x00\x0f")
END_OF_MESSAGE = encode_record(RecordType.END_OF_MESSAGE)


def cookies(count):
    return b"".join(encode_record(RecordType.NEW_COOKIE, bytes([i]) * 100, critical=False) for i in range(count))


def test_request():
    """Next Protocol NTPv4, AEAD_AES_SIV_CMAC_256 and End of Message, all critical (RFC 8915, section 4)."""
    assert build_request() == bytes.fromhex("800100020000" + "80040002000f" + "80000000")


@pytest.mark.parametrize(
    "extra,server,port",
    [
        (b"", None, None),
        (encode_record(RecordType.SERVER_NEGOTIATION, b"ntp.example.net"), "ntp.example.net", None),
        (encode_record(RecordType.PORT_NEGOTIATION, (1234).to_bytes(2, "big")), None, 1234),
        (encode_record(RecordType.WARNING, b"\x00\x01"), None, None),
        (encode_record(0x55, b"ignored", critical=False), None, None),
    ],
)
def test_response(extra, server, port):
    records = parse_records(NEXT_PROTOCOL_NTPV4 + AEAD_AES_SIV_CMAC_256 + cookies(8) + extra + END_OF_MESSAGE)

    assert interpret_response(records) == NTSKEResult(aead=15, cookies=8, server=server, port=port)


@pytest.mark.parametrize(
    "response,error",
    [
        (
            encode_record(RecordType.ERROR, b"\x00\x01") + END_OF_MESSAGE,
            "the server rejected the request (bad request)",
        ),
        (encode_record(RecordType.ERROR) + END_OF_MESSAGE, "the server rejected the request (no error code)"),
        (NEXT_PROTOCOL_NTPV4 + AEAD_AES_SIV_CMAC_256 + END_OF_MESSAGE, "the server sent no cookies"),
        (AEAD_AES_SIV_CMAC_256 + cookies(1) + END_OF_MESSAGE, "the server does not offer NTS for NTPv4"),
        (
            encode_record(RecordType.NEXT_PROTOCOL, b"\x80\x01") + AEAD_AES_SIV_CMAC_256 + cookies(1) + END_OF_MESSAGE,
            "the server does not offer NTS for NTPv4",
        ),
        (NEXT_PROTOCOL_NTPV4 + cookies(1) + END_OF_MESSAGE, "the server did not select an AEAD algorithm"),
        (
            NEXT_PROTOCOL_NTPV4 + AEAD_AES_SIV_CMAC_256 + cookies(1) + encode_record(0x55) + END_OF_MESSAGE,
            "the server sent an unrecognized critical record (type 85)",
        ),
        (
            NEXT_PROTOCOL_NTPV4
            + AEAD_AES_SIV_CMAC_256
            + cookies(1)
            + encode_record(RecordType.SERVER_NEGOTIATION, b"\xff")
            + END_OF_MESSAGE,
            "the server negotiated an NTP server name that is not ASCII",
        ),
        (
            NEXT_PROTOCOL_NTPV4 + encode_record(RecordType.AEAD_ALGORITHM, b"\x0f") + cookies(1) + END_OF_MESSAGE,
            "the server sent a malformed record (type 4)",
        ),
    ],
)
def test_rejected_response(response, error):
    with pytest.raises(NTSKEError, match=re.escape(error)):
        interpret_response(parse_records(response))


@pytest.mark.parametrize("cut", [1, 3, len(END_OF_MESSAGE), len(END_OF_MESSAGE) + 1])
def test_truncated_response(cut):
    """The client reads until the message is complete; anything short of that is an error, not a partial result."""
    response = (NEXT_PROTOCOL_NTPV4 + AEAD_AES_SIV_CMAC_256 + cookies(8) + END_OF_MESSAGE)[:-cut]

    assert split_records(response)[1] is False
    with pytest.raises(NTSKEError, match="the server's response was cut short"):
        parse_records(response)


def verification_error(code, message):
    error = ssl.SSLCertVerificationError(1, "certificate verify failed")
    error.verify_code = code
    error.verify_message = message
    return error


@pytest.mark.parametrize(
    "host,code,message,hint",
    [
        ("time.example.net", 10, "certificate has expired", " (check that the system clock is correct)"),
        ("time.example.net", 9, "certificate is not yet valid", " (check that the system clock is correct)"),
        (
            "192.0.2.1",
            64,
            "IP address mismatch, certificate is not valid for '192.0.2.1'.",
            " (an IP address must be listed in the certificate; use the hostname it was issued for)",
        ),
        ("time.example.net", 62, "Hostname mismatch, certificate is not valid for 'time.example.net'.", ""),
    ],
)
def test_certificate_error(host, code, message, hint):
    assert certificate_error(host, verification_error(code, message)) == (
        f"the server's TLS certificate was rejected: {message.rstrip('.')}{hint}"
    )


def test_connection_refused():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    with pytest.raises(NTSKEError, match="unable to connect to TCP port"):
        NTSKEClient("127.0.0.1", port=port, timeout=2).negotiate()


def test_server_without_tls():
    with socket.create_server(("127.0.0.1", 0)) as server:

        def serve():
            connection, _ = server.accept()
            with connection:
                connection.sendall(b"HTTP/1.0 400 Bad Request\r\n\r\n")

        thread = threading.Thread(target=serve)
        thread.start()
        try:
            with pytest.raises(NTSKEError, match="TLS handshake failed"):
                NTSKEClient("127.0.0.1", port=server.getsockname()[1], timeout=2).negotiate()
        finally:
            thread.join()
