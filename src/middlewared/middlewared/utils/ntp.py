"""Just enough of NTS key establishment (RFC 8915) to tell whether chrony would be able to use a server.

The probe performs the TLS handshake, which verifies the server's certificate against the system's trusted
certificate authorities as chrony does, and one request/response exchange that has to yield cookies for NTPv4.
The keys NTS derives from the TLS session are never used, so they are not exported.
"""

from __future__ import annotations

import dataclasses
import enum
import ipaddress
import socket
import ssl
import time

__all__ = ("NTSKE_PORT", "NTSKEClient", "NTSKEError", "NTSKERecord", "NTSKEResult", "probe_nts_ke")

NTSKE_PORT = 4460
NTSKE_ALPN = "ntske/1"
# A response is a handful of records plus eight cookies of a few hundred bytes each.
MAX_RESPONSE_SIZE = 65536

CRITICAL_BIT = 0x8000
PROTOCOL_NTPV4 = 0
AEAD_AES_SIV_CMAC_256 = 15
ERROR_CODES = {0: "unrecognized critical record", 1: "bad request", 2: "internal server error"}
# OpenSSL reasons for a server that will not speak TLS 1.3, which NTS key establishment requires.
TLS_VERSION_REASONS = {"TLSV1_ALERT_PROTOCOL_VERSION", "UNSUPPORTED_PROTOCOL"}
# OpenSSL verification results (`X509_V_ERR_*`) that point at the local clock rather than at the certificate.
X509_V_ERR_CERT_NOT_YET_VALID = 9
X509_V_ERR_CERT_HAS_EXPIRED = 10


class RecordType(enum.IntEnum):
    END_OF_MESSAGE = 0
    NEXT_PROTOCOL = 1
    ERROR = 2
    WARNING = 3
    AEAD_ALGORITHM = 4
    NEW_COOKIE = 5
    SERVER_NEGOTIATION = 6
    PORT_NEGOTIATION = 7


class NTSKEError(Exception):
    """Key establishment with the server failed. The message completes "NTS key establishment failed: ..."."""


@dataclasses.dataclass(frozen=True, slots=True)
class NTSKERecord:
    critical: bool
    rtype: int
    body: bytes


@dataclasses.dataclass(frozen=True, slots=True)
class NTSKEResult:
    aead: int
    cookies: int
    # Where to send NTP packets, if the server negotiated a host or port other than its own.
    server: str | None
    port: int | None


def encode_record(rtype: int, body: bytes = b"", *, critical: bool = True) -> bytes:
    header = (CRITICAL_BIT if critical else 0) | rtype
    return header.to_bytes(2, "big") + len(body).to_bytes(2, "big") + body


def build_request() -> bytes:
    """Ask for keys and cookies for NTPv4, protected with the one AEAD algorithm every server has to implement."""
    return (
        encode_record(RecordType.NEXT_PROTOCOL, PROTOCOL_NTPV4.to_bytes(2, "big"))
        + encode_record(RecordType.AEAD_ALGORITHM, AEAD_AES_SIV_CMAC_256.to_bytes(2, "big"))
        + encode_record(RecordType.END_OF_MESSAGE)
    )


def split_records(data: bytes) -> tuple[list[NTSKERecord], bool]:
    """Return the complete records at the start of `data`, and whether the last of them ends the message."""
    records: list[NTSKERecord] = []
    offset = 0
    while len(data) - offset >= 4:
        # A 16-bit type, whose top bit marks the record critical, then the 16-bit length of the body
        header = data[offset] << 8 | data[offset + 1]
        body_start = offset + 4
        body_end = body_start + (data[offset + 2] << 8 | data[offset + 3])
        if body_end > len(data):
            break

        record = NTSKERecord(bool(header & CRITICAL_BIT), header & ~CRITICAL_BIT, data[body_start:body_end])
        records.append(record)
        offset = body_end
        if record.rtype == RecordType.END_OF_MESSAGE:
            return records, True

    return records, False


def parse_records(data: bytes) -> list[NTSKERecord]:
    records, complete = split_records(data)
    if not complete:
        raise NTSKEError("the server's response was cut short")

    return records


def _u16_values(record: NTSKERecord) -> list[int]:
    body = record.body
    if len(body) % 2:
        raise NTSKEError(f"the server sent a malformed record (type {record.rtype})")

    return [body[i] << 8 | body[i + 1] for i in range(0, len(body), 2)]


def interpret_response(records: list[NTSKERecord]) -> NTSKEResult:
    protocols: list[int] = []
    aead: int | None = None
    cookies = 0
    server: str | None = None
    port: int | None = None
    for record in records:
        match record.rtype:
            case RecordType.END_OF_MESSAGE:
                break
            case RecordType.NEXT_PROTOCOL:
                protocols = _u16_values(record)
            case RecordType.ERROR:
                codes = _u16_values(record)
                reason = ERROR_CODES.get(codes[0], f"error code {codes[0]}") if codes else "no error code"
                raise NTSKEError(f"the server rejected the request ({reason})")
            case RecordType.WARNING:
                pass
            case RecordType.AEAD_ALGORITHM:
                aead = next(iter(_u16_values(record)), None)
            case RecordType.NEW_COOKIE:
                cookies += 1
            case RecordType.SERVER_NEGOTIATION:
                try:
                    server = record.body.decode("ascii") or None
                except UnicodeDecodeError:
                    raise NTSKEError("the server negotiated an NTP server name that is not ASCII") from None
            case RecordType.PORT_NEGOTIATION:
                port = next(iter(_u16_values(record)), None)
            case _:
                if record.critical:
                    raise NTSKEError(f"the server sent an unrecognized critical record (type {record.rtype})")

    if PROTOCOL_NTPV4 not in protocols:
        raise NTSKEError("the server does not offer NTS for NTPv4")
    if aead is None:
        raise NTSKEError("the server did not select an AEAD algorithm")
    if not cookies:
        raise NTSKEError("the server sent no cookies")

    return NTSKEResult(aead=aead, cookies=cookies, server=server, port=port)


def tls_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    # chrony verifies certificates with GnuTLS, which does not apply the RFC 5280 strictness OpenSSL turns on by
    # default since Python 3.13. Keeping it would reject certificates (from a private CA, say) that chrony accepts.
    context.verify_flags &= ~ssl.VERIFY_X509_STRICT
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.set_alpn_protocols([NTSKE_ALPN])
    return context


def certificate_error(host: str, error: ssl.SSLCertVerificationError) -> str:
    message = f"the server's TLS certificate was rejected: {error.verify_message.rstrip('.')}"
    if error.verify_code in (X509_V_ERR_CERT_HAS_EXPIRED, X509_V_ERR_CERT_NOT_YET_VALID):
        return f"{message} (check that the system clock is correct)"

    try:
        ipaddress.ip_address(host)
    except ValueError:
        return message

    return f"{message} (an IP address must be listed in the certificate; use the hostname it was issued for)"


@dataclasses.dataclass(slots=True)
class NTSKEClient:
    host: str
    port: int = NTSKE_PORT
    timeout: float = 5  # seconds, for the whole exchange

    def negotiate(self) -> NTSKEResult:
        deadline = time.monotonic() + self.timeout
        try:
            sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        except socket.gaierror as e:
            raise NTSKEError(f"unable to resolve {self.host}: {e.strerror}") from e
        except OSError as e:
            raise NTSKEError(f"unable to connect to TCP port {self.port}: {e.strerror or e}") from e

        with sock:
            try:
                sock.settimeout(self._remaining(deadline))
                tls = tls_context().wrap_socket(sock, server_hostname=self.host)
            except ssl.SSLCertVerificationError as e:
                raise NTSKEError(certificate_error(self.host, e)) from e
            except ssl.SSLError as e:
                if e.reason in TLS_VERSION_REASONS:
                    raise NTSKEError("the server does not support TLS 1.3") from e
                raise NTSKEError(f"TLS handshake failed: {e.reason or e}") from e
            except OSError as e:
                raise NTSKEError(f"TLS handshake failed: {e.strerror or e}") from e

            with tls:
                if tls.selected_alpn_protocol() != NTSKE_ALPN:
                    raise NTSKEError("the server does not support NTS key establishment")

                try:
                    response = self._exchange(tls, deadline)
                except OSError as e:
                    raise NTSKEError(f"no response from the server: {e.strerror or e}") from e

        return interpret_response(parse_records(response))

    def _exchange(self, tls: ssl.SSLSocket, deadline: float) -> bytes:
        tls.settimeout(self._remaining(deadline))
        tls.sendall(build_request())
        response = b""
        while not split_records(response)[1]:
            tls.settimeout(self._remaining(deadline))
            if not (chunk := tls.recv(4096)):
                break

            response += chunk
            if len(response) > MAX_RESPONSE_SIZE:
                raise NTSKEError("the server's response is too large")

        return response

    @staticmethod
    def _remaining(deadline: float) -> float:
        if (remaining := deadline - time.monotonic()) <= 0:
            raise TimeoutError("timed out")

        return remaining


def probe_nts_ke(host: str) -> NTSKEResult:
    """Run key establishment with `host` on the standard port. Raises `NTSKEError` if it fails."""
    return NTSKEClient(host).negotiate()
