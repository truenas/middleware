import base64
import contextlib
import time

import pytest
from truenas_api_client import ClientException

from middlewared.test.integration.utils import call, ssh

ROGUE_SMTP_PORT = 10025


@contextlib.contextmanager
def rogue_smtp_server(security):
    """
    A man-in-the-middle SMTP server with a self-signed certificate that no CA vouches for.
    It writes the credentials and messages it receives to the yielded file.
    """
    script = """\
import base64
import socket
import ssl
import sys

security, port, certfile, keyfile, captured = sys.argv[1:]
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain(certfile, keyfile)


def converse(sock):
    if security == "SSL":
        sock = context.wrap_socket(sock, server_side=True)

    lines = sock.makefile("rb")
    sock.sendall(b"220 smtp.example.com ESMTP\\r\\n")
    while line := lines.readline():
        verb, _, argument = line.decode().strip().partition(" ")
        match verb.upper():
            case "EHLO" if isinstance(sock, ssl.SSLSocket):
                sock.sendall(b"250-smtp.example.com\\r\\n250 AUTH PLAIN\\r\\n")
            case "EHLO":
                sock.sendall(b"250-smtp.example.com\\r\\n250 STARTTLS\\r\\n")
            case "STARTTLS":
                sock.sendall(b"220 Ready to start TLS\\r\\n")
                sock = context.wrap_socket(sock, server_side=True)
                lines = sock.makefile("rb")
            case "AUTH":
                _, user, password = base64.b64decode(argument.split()[1]).decode().split("\\0")
                with open(captured, "a") as f:
                    f.write(f"user={user} password={password}\\n")
                sock.sendall(b"235 Authentication successful\\r\\n")
            case "DATA":
                sock.sendall(b"354 End data with <CR><LF>.<CR><LF>\\r\\n")
                with open(captured, "ab") as f:
                    while (line := lines.readline()) != b".\\r\\n":
                        f.write(line)
                sock.sendall(b"250 OK\\r\\n")
            case "QUIT":
                sock.sendall(b"221 Bye\\r\\n")
                return
            case _:
                sock.sendall(b"250 OK\\r\\n")


listener = socket.create_server(("127.0.0.1", int(port)))
while True:
    sock = listener.accept()[0]
    try:
        converse(sock)
    except OSError:
        pass
    finally:
        sock.close()
"""
    call(
        "filesystem.file_receive",
        "/tmp/rogue_smtp.py",
        base64.b64encode(script.encode("ascii")).decode("ascii"),
        {"mode": 0o700},
    )
    ssh(
        "openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj /CN=smtp.example.com "
        "-keyout /tmp/rogue_smtp.key -out /tmp/rogue_smtp.crt >/dev/null 2>&1"
    )
    ssh("rm -f /tmp/rogue_smtp_captured && touch /tmp/rogue_smtp_captured")
    ssh(
        f"setsid python3 /tmp/rogue_smtp.py {security} {ROGUE_SMTP_PORT} /tmp/rogue_smtp.crt /tmp/rogue_smtp.key "
        "/tmp/rogue_smtp_captured < /dev/null > /dev/null 2>&1 &"
    )
    try:
        for _ in range(50):
            if "LISTEN" in ssh(f"ss -ltn sport = :{ROGUE_SMTP_PORT}", check=False):
                break

            time.sleep(0.1)
        else:
            pytest.fail(f"Rogue SMTP server did not start listening on port {ROGUE_SMTP_PORT}")

        yield "/tmp/rogue_smtp_captured"
    finally:
        ssh("pkill -f /tmp/rogue_smtp.py", check=False)
        ssh("rm -f /tmp/rogue_smtp.py /tmp/rogue_smtp.key /tmp/rogue_smtp.crt /tmp/rogue_smtp_captured", check=False)


def send_through_rogue_server(security, validate_certificate):
    call(
        "mail.send",
        {
            "subject": "Confidential report",
            "text": "Confidential report",
            "html": None,
            "to": ["admin@example.com"],
            "timeout": 10,
            "queue": False,
        },
        {
            "fromemail": "nas@example.com",
            "outgoingserver": "127.0.0.1",
            "port": ROGUE_SMTP_PORT,
            "security": security,
            "validate_certificate": validate_certificate,
            "smtp": True,
            "user": "smtp-user",
            "pass": "smtp-password",
            "oauth": None,
        },
        job=True,
    )


@pytest.mark.parametrize("security", ["SSL", "TLS"])
def test_send_refuses_server_with_untrusted_certificate(security):
    with rogue_smtp_server(security) as captured:
        with pytest.raises(ClientException, match="CERTIFICATE_VERIFY_FAILED"):
            send_through_rogue_server(security, True)

        assert ssh(f"cat {captured}") == ""


@pytest.mark.parametrize("security", ["SSL", "TLS"])
def test_send_accepts_untrusted_certificate_without_validation(security):
    with rogue_smtp_server(security) as captured:
        send_through_rogue_server(security, False)

        assert "user=smtp-user password=smtp-password" in ssh(f"cat {captured}")
