from __future__ import annotations

import base64
from email.message import Message
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, getaddresses, make_msgid
import errno
import html
import json
import logging
import os
import smtplib
import typing

import html2text

from middlewared.api.base.model import _NotRequired
from middlewared.api.current import MailEntry, MailSendMessage, MailUpdate
from middlewared.service import CallError, NetworkActivityDisabled, ServiceContext, ValidationError
from middlewared.utils import ProductName
from middlewared.utils.mako import get_template

from .config import validate_config
from .gmail import gmail
from .message import from_addr
from .queue import MailQueue
from .smtp import get_smtp_server

if typing.TYPE_CHECKING:
    from middlewared.job import Job

logger = logging.getLogger(__name__)


def send(
    context: ServiceContext,
    mail_queue: MailQueue,
    job: Job,
    request: MailSendMessage,
    extra_config: MailUpdate,
) -> None:
    message = {k: v for k, v in request.model_dump().items() if not isinstance(v, _NotRequired)}

    gc = context.middleware.call_sync("datastore.config", "network.globalconfiguration")
    hostname = f"{gc['gc_hostname']}.{gc['gc_domain']}"
    message["subject"] = f"{ProductName.PRODUCT_NAME} {hostname}: {message['subject']}"
    add_html = True
    if "html" in message and message["html"] is None:
        message.pop("html")
        add_html = False

    if "text" not in message:
        if "html" not in message:
            raise ValidationError("text", "Text is required when HTML is not set")

        message["text"] = html2text.html2text(message["html"])

    if add_html and "html" not in message:
        template = get_template("assets/templates/mail.html")
        message["html"] = template.render(
            body=(
                '<div style="font-family: monospace; white-space: pre-wrap;">' + html.escape(message["text"]) + "</div>"
            )
        )

    config = context.call_sync2(context.s.mail.config).updated(extra_config)

    from_addr_ = from_addr(config)

    validate_config(config)

    to = message.get("to")
    if not to:
        to = context.call_sync2(context.s.mail.local_administrators_emails)
        if not to:
            raise CallError("None of the local administrators has an e-mail address configured")

    if message.get("attachments"):
        job.check_pipe("input")

        def read_json() -> typing.Any:
            f = job.pipes.input.r
            data = b""
            i = 0
            while True:
                read = f.read(1048576)  # 1MiB
                if read == b"":
                    break
                data += read
                i += 1
                if i > 50:
                    raise ValidationError("attachments", "Attachments bigger than 50MB not allowed yet")

            if data == b"":
                return None

            try:
                return json.loads(data)
            except ValueError as e:
                raise ValidationError("attachments", f"Attachments are not valid JSON: {e}")

        attachments = read_json()
        if attachments is not None and not isinstance(attachments, list):
            raise ValidationError("attachments", "Attachments must be an array")
    else:
        attachments = None

    if "html" in message or attachments:
        msg: MIMEBase = MIMEMultipart()
        msg.preamble = "This is a multi-part message in MIME format."
        if "html" in message:
            msg2 = MIMEMultipart("alternative")
            msg2.attach(MIMEText(message["text"], "plain", _charset="utf-8"))
            msg2.attach(MIMEText(message["html"], "html", _charset="utf-8"))
            msg.attach(msg2)
        if attachments:
            for index, attachment in enumerate(attachments):
                msg.attach(build_attachment(index, attachment))
    else:
        msg = MIMEText(message["text"], _charset="utf-8")

    msg["Subject"] = message["subject"]

    msg["From"] = from_addr_
    msg["To"] = ", ".join(to)
    if message.get("cc"):
        msg["Cc"] = ", ".join(message["cc"])
    msg["Date"] = formatdate()

    local_hostname = context.middleware.call_sync("system.hostname")

    msg["Message-ID"] = make_msgid(base64.urlsafe_b64encode(os.urandom(3)).decode("ascii"))

    extra_headers = message.get("extra_headers") or {}
    for key, val in list(extra_headers.items()):
        # We already have "Content-Type: multipart/mixed" and setting "Content-Type: text/plain" like some scripts
        # do will break python e-mail module.
        if key.lower() == "content-type":
            continue

        if key in msg:
            msg.replace_header(key, val)
        else:
            msg[key] = val

    try:
        sendmail(context, msg, config, message["timeout"], local_hostname)
    except NetworkActivityDisabled:
        logger.warning("Sending email denied")
        raise
    except Exception as e:
        # We are only interested in ValueError, not subclasses.
        if e.__class__ is ValueError:
            raise CallError(str(e))
        if isinstance(e, smtplib.SMTPAuthenticationError):
            raise CallError(f"Authentication error ({e.smtp_code}): {e.smtp_error!r}", errno.EPERM)

        # NAS-137666: Email addresses are considered Personally Identifiable
        # Information (PII) under GDPR. Prevent displaying them in logs.
        if isinstance(e, smtplib.SMTPSenderRefused):
            e.sender = "[sender redacted]"
            e.args = (e.smtp_code, e.smtp_error, e.sender)
        elif isinstance(e, smtplib.SMTPRecipientsRefused):
            e.recipients = {"": (0, b"[recipient info redacted]")}
            e.args = (e.recipients,)

        logger.warning("Failed to send email", exc_info=e)
        if message["queue"]:
            with mail_queue as mq:
                mq.append(msg)

        raise CallError(f"Failed to send email: {e}")


def build_attachment(index: int, attachment: typing.Any) -> Message:
    """Build a MIME part from one caller-supplied attachment.

    Attachments are uploaded as JSON rather than passed through the API model, so nothing has
    validated their shape yet.
    """
    m = Message()
    try:
        m.set_payload(attachment["content"])
        for header in attachment.get("headers") or []:
            m.add_header(header["name"], header["value"], **(header.get("params") or {}))
    except (AttributeError, KeyError, TypeError) as e:
        raise ValidationError("attachments", f"Invalid attachment at index {index}: {e!r}")

    return m


def envelope_recipients(msg: MIMEBase) -> list[str]:
    """Return every address `msg` should be delivered to, in order and without duplicates.

    SMTP delivers to the envelope recipients, not to the message headers, so `Cc` has to be
    included here or those recipients would never receive the message.
    """
    recipients = []
    for _, address in getaddresses(msg.get_all("To", []) + msg.get_all("Cc", [])):
        if address and address not in recipients:
            recipients.append(address)

    return recipients


def sendmail(
    context: ServiceContext,
    msg: MIMEBase,
    config: MailEntry,
    timeout: int = 300,
    local_hostname: str | None = None,
) -> None:
    oauth = config.oauth.get_secret_value()
    if oauth and oauth.provider == "gmail":
        gmail.send(context, msg, config)
    else:
        with get_smtp_server(context, config, timeout, local_hostname) as server:
            # NOTE: Don't do this.
            #
            # If smtplib.SMTP* tells you to run connect() first, it"s because the
            # mailserver it tried connecting to via the outgoing server argument
            # was unreachable, and it tried to connect to "localhost" and barfed.
            # This is because we don't run a full MTA.
            # else:
            #    server.connect()
            # The envelope sender is an address, not the `From` header, which may carry a display
            # name and be RFC 2047 encoded.
            server.sendmail(
                config.fromemail,
                envelope_recipients(msg),
                msg.as_string(),
            )
