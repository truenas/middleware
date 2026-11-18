import contextlib
import functools
import smtplib
import ssl
from typing import Callable, Generator

from middlewared.api.current import MailEntry
from middlewared.service import ServiceContext

from .outlook import outlook


@contextlib.contextmanager
def get_smtp_server(
    context: ServiceContext,
    config: MailEntry,
    timeout: int = 300,
    local_hostname: str | None = None,
) -> Generator[smtplib.SMTP, None, None]:
    context.middleware.call_sync("network.general.will_perform_activity", "mail")

    if local_hostname is None:
        local_hostname = context.middleware.call_sync("system.hostname")

    if not config.outgoingserver or not config.port:
        raise ValueError("You must provide an outgoing mailserver and mail server port when sending mail")

    ssl_context = ssl.create_default_context()
    if not config.validate_certificate:
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

    if config.security == "SSL":
        factory: Callable[..., smtplib.SMTP] = functools.partial(smtplib.SMTP_SSL, context=ssl_context)
    else:
        factory = smtplib.SMTP

    with factory(
        config.outgoingserver,
        config.port,
        timeout=timeout,
        local_hostname=local_hostname,
    ) as server:
        if config.security == "TLS":
            server.starttls(context=ssl_context)

        oauth = config.oauth.get_secret_value()
        if oauth and oauth.provider == "outlook":
            outlook.xoauth2(server, config)
        elif config.smtp:
            username: str = config.user  # type: ignore[assignment]
            password: str = config.pass_.get_secret_value() or ""
            server.login(username, password)

        yield server
