from __future__ import annotations

from typing import TYPE_CHECKING

from middlewared.api import api_method
from middlewared.api.current import (
    MailEntry,
    MailLocalAdministratorEmailArgs,
    MailLocalAdministratorEmailResult,
    MailSendArgs,
    MailSendMessage,
    MailSendResult,
    MailUpdate,
    MailUpdateArgs,
    MailUpdateResult,
)
from middlewared.service import (
    GenericConfigService,
    ServiceContext,
    job,
    periodic,
    private,
)

from .config import MailConfigServicePart
from .gmail import gmail
from .queue import MailQueue
from .send import send
from .send_queue import send_mail_queue

if TYPE_CHECKING:
    from middlewared.job import Job
    from middlewared.main import Middleware


class MailService(GenericConfigService[MailEntry]):
    class Config:
        namespace = "mail"
        cli_namespace = "system.mail"
        role_prefix = "ALERT"
        entry = MailEntry
        generic = True

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._mail_queue = MailQueue()
        self._svc_part = MailConfigServicePart(self.context)

    @api_method(MailUpdateArgs, MailUpdateResult, check_annotations=True)
    async def do_update(self, data: MailUpdate) -> MailEntry:
        """Update Mail Service Configuration."""
        return await self._svc_part.do_update(data)

    @api_method(MailSendArgs, MailSendResult, roles=["MAIL_WRITE"], check_annotations=True)
    @job(pipes=["input"], check_pipes=False)
    def send(self, job: Job, message: MailSendMessage, config: MailUpdate | None = None) -> None:
        """Sends mail using configured mail settings."""
        return send(self.context, self._mail_queue, job, message, config or MailUpdate())  # type: ignore[call-arg]

    @periodic(600, run_on_start=False)
    @private
    def send_mail_queue(self) -> None:
        send_mail_queue(self.context, self._mail_queue)

    @private
    async def local_administrators_emails(self) -> list[str]:
        return list(
            set(
                user["email"]
                for user in await self.middleware.call(
                    "user.query", [["roles", "rin", "FULL_ADMIN"], ["local", "=", True], ["email", "!=", None]]
                )
            )
        )

    @api_method(
        MailLocalAdministratorEmailArgs,
        MailLocalAdministratorEmailResult,
        roles=["ALERT_READ"],
        check_annotations=True,
    )
    async def local_administrator_email(self) -> str | None:
        """
        Return the email address of the local administrator.

        The local administrator is a local user account holding the ``FULL_ADMIN`` role that has an
        email address configured. When more than one such account exists, the address that sorts
        first alphabetically is returned. ``null`` is returned when no local administrator has an
        email address set.
        """
        emails = await self.local_administrators_emails()
        if emails:
            return sorted(emails)[0]
        else:
            return None


async def setup(middleware: Middleware) -> None:
    await middleware.call("network.general.register_activity", "mail", "Mail")
    await middleware.run_in_thread(gmail.initialize, ServiceContext(middleware, middleware.logger))
