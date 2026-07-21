import base64
import contextlib
import email.header
import email.utils
import io
import json
import re

import pytest
from truenas_api_client import ClientException

from middlewared.test.integration.assets.account import user
from middlewared.test.integration.assets.mail import fake_smtp_server
from middlewared.test.integration.fake_servers.smtp import (
    AUTH_PASSWORD,
    AUTH_USER,
    REFUSE_RECIPIENT,
    REFUSE_SENDER,
)
from middlewared.test.integration.utils import call, mock, session, url
# `mail.update` is a plain call, so the client re-raises the original middleware exception, while
# `mail.send` is a job, whose failures always surface as a `truenas_api_client` exception.
from middlewared.service_exception import ValidationError

FROM_EMAIL = "truenas@localhost"
FROM_NAME = "TrueNAS Test"
TO = "recipient@example.com"
ADMIN_USER = "mailadmin"
ADMIN_EMAIL = "mailadmin@ixsystems.com"
ADMIN_PASSWORD = "abcd1234"


def base_config(server, **overrides):
    """Mail configuration pointing at the fake SMTP `server`, with `overrides` applied."""
    return {
        "fromemail": FROM_EMAIL,
        "fromname": FROM_NAME,
        "outgoingserver": server.host,
        "port": server.port,
        "security": "PLAIN",
        "smtp": False,  # no authentication needed against the fake server
        "user": "",
        "pass": "",
        **overrides,
    }


def message(**overrides):
    return {"subject": "test subject", "text": "test body", "to": [TO], "queue": False, **overrides}


@pytest.fixture(scope="module", autouse=True)
def restore_mail_config():
    original = call("mail.config")
    try:
        yield
    finally:
        call("mail.update", {k: v for k, v in original.items() if k != "id"})


@pytest.fixture(scope="module")
def smtp_server(restore_mail_config):
    with fake_smtp_server() as server:
        yield server


@pytest.fixture
def server(smtp_server):
    """The fake SMTP server, with the mail configuration pointed at it and no messages recorded."""
    call("mail.update", base_config(smtp_server))
    smtp_server.clear()
    return smtp_server


@contextlib.contextmanager
def no_administrator_emails():
    """Temporarily strip the email address off every local full administrator."""
    admins = call("user.query", [["roles", "rin", "FULL_ADMIN"], ["local", "=", True], ["email", "!=", None]])
    for admin in admins:
        call("user.update", admin["id"], {"email": None})
    try:
        yield
    finally:
        for admin in admins:
            call("user.update", admin["id"], {"email": admin["email"]})


@pytest.fixture
def administrator_email():
    """`ADMIN_EMAIL` is the only local administrator email address for the duration of the test."""
    builtin_administrators = call("group.query", [["gid", "=", 544]], {"get": True})["id"]
    with no_administrator_emails():
        with user({
            "username": ADMIN_USER,
            "full_name": ADMIN_USER,
            "group_create": False,
            "group": builtin_administrators,
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD,
        }):
            yield ADMIN_EMAIL


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


@pytest.mark.parametrize("user", ["", None])
def test_update_requires_user_when_smtp_authentication_is_enabled(server, user):
    with pytest.raises(ValidationError, match="user: This field is required when SMTP authentication is enabled"):
        call("mail.update", {"smtp": True, "user": user})


@pytest.mark.parametrize("password", ["", None])
def test_mail_send_with_unset_password(server, password):
    """An unset password is allowed; it just fails to authenticate rather than crashing."""
    with pytest.raises(ClientException, match=r"Authentication error \(535\)"):
        call("mail.send", message(), {"smtp": True, "user": AUTH_USER, "pass": password}, job=True)


def test_update_requires_fromemail(server):
    with pytest.raises(ValidationError, match="fromemail: This field is required"):
        call("mail.update", {"fromemail": ""})


def test_update_rejects_non_ascii_password(server):
    with pytest.raises(ValidationError, match="pass: Only plain text characters"):
        call("mail.update", {"pass": "пароль"})


def test_mail_send(server):
    call("mail.send", message(
        cc=["cc@example.com"],
        extra_headers={"X-Custom": "custom-value"},
    ), job=True)
    messages = server.get_messages()

    nc = call("network.configuration.config")
    hostname = f"{nc['hostname']}.{nc['domain']}"
    expected_html = (
        '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0 Transitional//EN">\n\n'
        '<div style="font-family: monospace; white-space: pre-wrap;">test body</div>\n'
    )

    assert len(messages) == 1
    mail = messages[0]

    # SMTP envelope. Cc recipients are delivered to as well as being listed in the header.
    assert mail.mail_from == FROM_EMAIL
    assert mail.rcpt_to == [TO, "cc@example.com"]

    msg = mail.message

    # Every top-level header.
    assert set(msg.keys()) == {
        "Content-Type", "MIME-Version", "Subject", "From", "To", "Cc", "Date",
        "Message-ID", "X-Custom",
    }
    assert msg.get_content_type() == "multipart/mixed"
    assert msg["MIME-Version"] == "1.0"
    assert msg["Subject"] == f"TrueNAS {hostname}: test subject"
    assert msg["From"] == f"{FROM_NAME} <{FROM_EMAIL}>"
    assert msg["To"] == TO
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


def test_mail_send_cc_recipients_are_in_the_envelope(server):
    """SMTP delivers to the envelope, so every Cc address must appear in RCPT TO."""
    call("mail.send", message(
        to=["first@example.com", "second@example.com"],
        cc=["third@example.com", "fourth@example.com"],
    ), job=True)

    mail = server.get_messages()[0]
    assert mail.rcpt_to == ["first@example.com", "second@example.com", "third@example.com", "fourth@example.com"]
    assert mail.message["To"] == "first@example.com, second@example.com"
    assert mail.message["Cc"] == "third@example.com, fourth@example.com"


def test_mail_send_duplicate_recipients_are_delivered_to_once(server):
    """An address in both To and Cc must not be handed to the server twice."""
    call("mail.send", message(to=[TO], cc=[TO, "cc@example.com"]), job=True)

    assert server.get_messages()[0].rcpt_to == [TO, "cc@example.com"]


def test_mail_send_queued_message_keeps_cc_recipients(server):
    """The Cc envelope recipients survive a trip through the retry queue."""
    call("mail.update", base_config(server, port=1))
    with pytest.raises(ClientException, match="Failed to send email"):
        call("mail.send", message(cc=["cc@example.com"], queue=True), job=True)

    call("mail.update", base_config(server))
    call("mail.send_mail_queue")

    assert server.get_messages()[0].rcpt_to == [TO, "cc@example.com"]


def test_mail_send_html_only(server):
    """When only HTML is given, the plain text part is derived from it."""
    call("mail.send", {
        "subject": "test subject",
        "html": "<p>Hello <b>world</b></p>",
        "to": [TO],
        "queue": False,
    }, job=True)

    parts = list(server.get_messages()[0].message.walk())
    assert [part.get_content_type() for part in parts] == [
        "multipart/mixed", "multipart/alternative", "text/plain", "text/html",
    ]
    assert parts[2].get_payload(decode=True).decode().strip() == "Hello **world**"
    assert parts[3].get_payload(decode=True).decode() == "<p>Hello <b>world</b></p>"


def test_mail_send_without_html(server):
    """`html: null` suppresses the HTML part entirely, producing a bare text/plain message."""
    call("mail.send", message(html=None), job=True)

    msg = server.get_messages()[0].message
    assert not msg.is_multipart()
    assert msg.get_content_type() == "text/plain"
    assert msg.get_payload(decode=True).decode() == "test body"


def test_mail_send_requires_text_or_html(server):
    with pytest.raises(ClientException, match="Text is required when HTML is not set"):
        call("mail.send", {"subject": "test subject", "to": [TO], "queue": False}, job=True)

    assert server.get_messages() == []


def test_mail_send_non_ascii_fromname(server):
    call("mail.send", message(), {"fromname": "Тест"}, job=True)

    mail = server.get_messages()[0]
    assert mail.mail_from == FROM_EMAIL
    decoded = str(email.header.make_header(email.header.decode_header(mail.message["From"])))
    assert decoded == f"Тест <{FROM_EMAIL}>"


def test_mail_send_without_fromname(server):
    call("mail.send", message(), {"fromname": ""}, job=True)

    assert server.get_messages()[0].message["From"] == FROM_EMAIL


def test_mail_send_non_ascii_fromemail_without_fromname(server):
    """A non-ASCII `fromemail` cannot be used as an envelope sender, and fails rather than
    silently putting the RFC 2047 encoded header into MAIL FROM."""
    with pytest.raises(ClientException, match="ascii"):
        call("mail.send", message(), {"fromname": "", "fromemail": "тест@localhost"}, job=True)

    assert server.get_messages() == []


def test_mail_send_extra_headers(server):
    """`extra_headers` replaces existing headers and adds new ones, but never overrides Content-Type."""
    call("mail.send", message(extra_headers={
        "Content-Type": "text/plain",
        "Subject": "replaced subject",
        "X-New": "new value",
    }), job=True)

    msg = server.get_messages()[0].message
    assert msg["Subject"] == "replaced subject"
    assert msg["X-New"] == "new value"
    assert len(msg.get_all("Content-Type")) == 1
    assert msg.get_content_type() == "multipart/mixed"


ATTACHMENTS = [{
    "headers": [
        {"name": "Content-Transfer-Encoding", "value": "base64"},
        {"name": "Content-Type", "value": "application/octet-stream", "params": {"name": "test.txt"}},
    ],
    "content": base64.b64encode(b"attachment contents\n").decode(),
}]


def send_with_attachments(payload, body):
    """Call `mail.send` with `body` as the attachments upload, and wait for the job."""
    with session() as s:
        r = s.post(
            f"{url()}/_upload",
            files={
                "data": (None, io.StringIO(json.dumps({"method": "mail.send", "params": [payload]}))),
                "file": (None, io.BytesIO(body)),
            },
        )
        r.raise_for_status()
        job_id = r.json()["job_id"]

    call("core.job_wait", job_id, job=True)


def test_mail_send_attachments(server):
    send_with_attachments(message(attachments=True), json.dumps(ATTACHMENTS).encode())

    parts = list(server.get_messages()[0].message.walk())
    assert [part.get_content_type() for part in parts] == [
        "multipart/mixed", "multipart/alternative", "text/plain", "text/html",
        "application/octet-stream",
    ]
    assert parts[4]["Content-Type"] == 'application/octet-stream; name="test.txt"'
    assert parts[4].get_payload(decode=True) == b"attachment contents\n"


def test_mail_send_attachments_without_html(server):
    send_with_attachments(message(attachments=True, html=None), json.dumps(ATTACHMENTS).encode())

    parts = list(server.get_messages()[0].message.walk())
    assert [part.get_content_type() for part in parts] == ["multipart/mixed", "application/octet-stream"]
    assert parts[1].get_payload(decode=True) == b"attachment contents\n"


def test_mail_send_empty_attachments(server):
    """An empty upload is treated as no attachments at all."""
    send_with_attachments(message(attachments=True), b"")

    parts = list(server.get_messages()[0].message.walk())
    assert [part.get_content_type() for part in parts] == [
        "multipart/mixed", "multipart/alternative", "text/plain", "text/html",
    ]


def test_mail_send_attachment_without_headers(server):
    """`headers` is optional: an attachment can be a bare payload."""
    send_with_attachments(message(attachments=True), json.dumps([{"content": "dGVzdAo="}]).encode())

    parts = list(server.get_messages()[0].message.walk())
    assert [part.get_content_type() for part in parts] == [
        "multipart/mixed", "multipart/alternative", "text/plain", "text/html", "text/plain",
    ]
    assert parts[4].get_payload() == "dGVzdAo="


def test_mail_send_attachment_without_content(server):
    """Attachments are uploaded as free-form JSON, so a missing key must not escape as a traceback."""
    with pytest.raises(ClientException, match="Invalid attachment at index 0"):
        send_with_attachments(message(attachments=True), json.dumps([{"headers": []}]).encode())


@pytest.mark.parametrize("content", [1, None, ["dGVzdAo="], {"data": "dGVzdAo="}])
def test_mail_send_attachment_content_not_a_string(server, content):
    """A non-string payload would otherwise only fail when the message is flattened for sending."""
    with pytest.raises(ClientException, match="Invalid attachment at index 0: content must be a string"):
        send_with_attachments(message(attachments=True), json.dumps([{"content": content}]).encode())


def test_mail_send_attachment_not_an_object(server):
    with pytest.raises(ClientException, match="Invalid attachment at index 0"):
        send_with_attachments(message(attachments=True), json.dumps(["dGVzdAo="]).encode())


def test_mail_send_attachments_not_an_array(server):
    with pytest.raises(ClientException, match="Attachments must be an array"):
        send_with_attachments(message(attachments=True), json.dumps({"content": "dGVzdAo="}).encode())


def test_mail_send_attachments_invalid_json(server):
    with pytest.raises(ClientException, match="Attachments are not valid JSON"):
        send_with_attachments(message(attachments=True), b"{not json")


def test_local_administrator_email(administrator_email):
    assert call("mail.local_administrators_emails") == [administrator_email]
    assert call("mail.local_administrator_email") == administrator_email


def test_local_administrator_email_unset():
    with no_administrator_emails():
        assert call("mail.local_administrators_emails") == []
        assert call("mail.local_administrator_email") is None


def test_mail_send_defaults_to_local_administrators(server, administrator_email):
    call("mail.send", {"subject": "test subject", "text": "test body", "queue": False}, job=True)

    mail = server.get_messages()[0]
    assert mail.rcpt_to == [administrator_email]
    assert mail.message["To"] == administrator_email


def test_mail_send_without_recipients(server):
    with no_administrator_emails():
        with pytest.raises(ClientException, match="None of the local administrators has an e-mail address configured"):
            call("mail.send", {"subject": "test subject", "text": "test body", "queue": False}, job=True)


def test_mail_send_without_outgoingserver(server):
    with pytest.raises(ClientException, match="You must provide an outgoing mailserver and mail server port"):
        call("mail.send", message(), {"outgoingserver": ""}, job=True)


def test_mail_send_with_smtp_authentication(server):
    call("mail.send", message(), {"smtp": True, "user": AUTH_USER, "pass": AUTH_PASSWORD}, job=True)

    assert len(server.get_messages()) == 1


def test_mail_send_with_invalid_smtp_credentials(server):
    with pytest.raises(ClientException, match=r"Authentication error \(535\)"):
        call("mail.send", message(), {"smtp": True, "user": AUTH_USER, "pass": "wrong password"}, job=True)

    assert server.get_messages() == []


def test_mail_send_ssl(server):
    """The fake server speaks plain text, so an SSL connection to it fails during the handshake."""
    with pytest.raises(ClientException, match="Failed to send email"):
        call("mail.send", message(timeout=10), {"security": "SSL"}, job=True)

    assert server.get_messages() == []


def test_mail_send_starttls(server):
    """The fake server does not advertise STARTTLS, so `security: TLS` fails to negotiate."""
    with pytest.raises(ClientException, match="Failed to send email"):
        call("mail.send", message(timeout=10), {"security": "TLS"}, job=True)

    assert server.get_messages() == []


def test_mail_send_sender_refused_redacts_sender(server):
    """Email addresses are PII and must not appear in the error."""
    with pytest.raises(ClientException) as ve:
        call("mail.send", message(), {"fromemail": f"{REFUSE_SENDER}@localhost"}, job=True)

    assert "[sender redacted]" in ve.value.error
    assert REFUSE_SENDER not in ve.value.error


def test_mail_send_recipients_refused_redacts_recipients(server):
    """Email addresses are PII and must not appear in the error."""
    with pytest.raises(ClientException) as ve:
        call("mail.send", message(to=[f"{REFUSE_RECIPIENT}@example.com"]), job=True)

    assert "[recipient info redacted]" in ve.value.error
    assert REFUSE_RECIPIENT not in ve.value.error


def test_mail_send_network_activity_disabled(server):
    with mock("network.general.can_perform_activity", return_value=False):
        with pytest.raises(ClientException, match="is disabled"):
            call("mail.send", message(), job=True)

    assert server.get_messages() == []


def test_mail_send_queue_is_retried(server):
    """A message that fails to send with `queue: true` is retried by `mail.send_mail_queue`."""
    call("mail.update", base_config(server, port=1))
    with pytest.raises(ClientException, match="Failed to send email"):
        call("mail.send", message(subject="queued subject", queue=True), job=True)
    assert server.get_messages() == []

    call("mail.update", base_config(server))
    call("mail.send_mail_queue")

    messages = server.get_messages()
    assert len(messages) == 1
    assert messages[0].message["Subject"].endswith("queued subject")
    # The `From` address is refreshed from the current configuration before each retry.
    assert messages[0].message["From"] == f"{FROM_NAME} <{FROM_EMAIL}>"


def test_mail_send_queue_gives_up_after_max_attempts(server):
    call("mail.update", base_config(server, port=1))
    with pytest.raises(ClientException, match="Failed to send email"):
        call("mail.send", message(queue=True), job=True)

    # `MailQueue.MAX_ATTEMPTS` failed retries drop the message from the queue.
    for _ in range(3):
        call("mail.send_mail_queue")

    call("mail.update", base_config(server))
    call("mail.send_mail_queue")
    assert server.get_messages() == []


def test_mail_send_queue_dropped_when_network_activity_disabled(server):
    call("mail.update", base_config(server, port=1))
    with pytest.raises(ClientException, match="Failed to send email"):
        call("mail.send", message(queue=True), job=True)

    call("mail.update", base_config(server))
    with mock("network.general.can_perform_activity", return_value=False):
        call("mail.send_mail_queue")

    call("mail.send_mail_queue")
    assert server.get_messages() == []
