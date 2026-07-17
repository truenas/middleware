import email.utils
import re

from middlewared.test.integration.assets.mail import fake_smtp_server
from middlewared.test.integration.utils import call


def test_config_settings():
    payload = {
        "fromemail": "william.spam@ixsystems.com",
        "outgoingserver": "mail.ixsystems.com",
        "pass": "changeme",
        "port": 25,
        "security": "PLAIN",
        "smtp": True,
        "user": "william.spam@ixsystems.com"
    }
    call("mail.update", payload)
    config = call("mail.config")
    # test that payload is a subset of config
    assert payload.items() <= config.items()


def test_mail_send():
    with fake_smtp_server() as server:
        call("mail.update", {
            "fromemail": "truenas@localhost",
            "fromname": "TrueNAS Test",
            "outgoingserver": server.host,
            "port": server.port,
            "security": "PLAIN",
            "smtp": False,  # no authentication needed against the fake server
        })
        call("mail.send", {
            "subject": "test subject",
            "text": "test body",
            "to": ["recipient@example.com"],
            "cc": ["cc@example.com"],
            "queue": False,
            "extra_headers": {"X-Custom": "custom-value"},
        }, job=True)
        messages = server.get_messages()

    nc = call("network.configuration.config")
    hostname = f"{nc['hostname']}.{nc['domain']}"
    expected_html = (
        '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0 Transitional//EN">\n\n'
        '<div style="font-family: monospace; white-space: pre-wrap;">test body</div>\n'
    )

    assert len(messages) == 1
    mail = messages[0]

    # SMTP envelope. Cc recipients are a header only, not part of the envelope.
    assert mail.mail_from == "truenas@localhost"
    assert mail.rcpt_to == ["recipient@example.com"]

    msg = mail.message

    # Every top-level header.
    assert set(msg.keys()) == {
        "Content-Type", "MIME-Version", "Subject", "From", "To", "Cc", "Date",
        "Message-ID", "X-Custom",
    }
    assert msg.get_content_type() == "multipart/mixed"
    assert msg["MIME-Version"] == "1.0"
    assert msg["Subject"] == f"TrueNAS {hostname}: test subject"
    assert msg["From"] == "TrueNAS Test <truenas@localhost>"
    assert msg["To"] == "recipient@example.com"
    assert msg["Cc"] == "cc@example.com"
    assert msg["X-Custom"] == "custom-value"
    # Date and Message-ID are generated per-message; assert they are well-formed.
    assert email.utils.parsedate_to_datetime(msg["Date"]) is not None
    assert re.fullmatch(r"<[^@<>]+@[^@<>]+>", msg["Message-ID"])

    # Every MIME part, in walk() order.
    parts = list(msg.walk())
    assert [part.get_content_type() for part in parts] == [
        "multipart/mixed",
        "multipart/alternative",
        "text/plain",
        "text/html",
    ]

    alternative = parts[1]
    assert set(alternative.keys()) == {"Content-Type", "MIME-Version"}
    assert alternative["Content-Type"].startswith('multipart/alternative; boundary=')
    assert alternative["MIME-Version"] == "1.0"

    text_part = parts[2]
    assert set(text_part.keys()) == {"Content-Type", "MIME-Version", "Content-Transfer-Encoding"}
    assert text_part["Content-Type"] == 'text/plain; charset="utf-8"'
    assert text_part["MIME-Version"] == "1.0"
    assert text_part["Content-Transfer-Encoding"] == "base64"
    assert text_part.get_payload(decode=True).decode() == "test body"

    html_part = parts[3]
    assert set(html_part.keys()) == {"Content-Type", "MIME-Version", "Content-Transfer-Encoding"}
    assert html_part["Content-Type"] == 'text/html; charset="utf-8"'
    assert html_part["MIME-Version"] == "1.0"
    assert html_part["Content-Transfer-Encoding"] == "base64"
    assert html_part.get_payload(decode=True).decode() == expected_html
