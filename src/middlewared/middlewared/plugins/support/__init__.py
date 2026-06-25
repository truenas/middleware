from __future__ import annotations

from typing import TYPE_CHECKING

from middlewared.api import api_method
from middlewared.api.current import (
    SupportAttachTicket,
    SupportAttachTicketArgs,
    SupportAttachTicketMaxSizeArgs,
    SupportAttachTicketMaxSizeResult,
    SupportAttachTicketResult,
    SupportEntry,
    SupportFieldsArgs,
    SupportFieldsResult,
    SupportIsAvailableAndEnabledArgs,
    SupportIsAvailableAndEnabledResult,
    SupportIsAvailableArgs,
    SupportIsAvailableResult,
    SupportNewTicket,
    SupportNewTicketArgs,
    SupportNewTicketCommunity,
    SupportNewTicketEnterprise,
    SupportNewTicketResult,
    SupportSimilarIssue,
    SupportSimilarIssuesArgs,
    SupportSimilarIssuesResult,
    SupportUpdate,
    SupportUpdateArgs,
    SupportUpdateResult,
)
from middlewared.plugins.system.utils import DEBUG_MAX_SIZE
from middlewared.service import GenericConfigService, job

from .config import SupportConfigServicePart
from .execute import attach_ticket, new_ticket, similar_issues

if TYPE_CHECKING:
    from middlewared.job import Job
    from middlewared.main import Middleware

__all__ = ("SupportService",)


class SupportService(GenericConfigService[SupportEntry]):
    class Config:
        cli_namespace = "system.support"
        entry = SupportEntry
        generic = True
        role_prefix = "SUPPORT"

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = SupportConfigServicePart(self.context)

    @api_method(SupportUpdateArgs, SupportUpdateResult, check_annotations=True)
    async def do_update(self, data: SupportUpdate) -> SupportEntry:
        """
        Update Proactive Support settings.
        """
        return await self._svc_part.do_update(data)

    @api_method(SupportIsAvailableArgs, SupportIsAvailableResult, roles=["SUPPORT_READ"], check_annotations=True)
    async def is_available(self) -> bool:
        """
        Returns whether Proactive Support is available for this product type and current license.
        """
        if await self.call2(self.s.system.vendor.name):
            return False

        return bool(await self.middleware.call("system.has_support_contract"))

    @api_method(
        SupportIsAvailableAndEnabledArgs,
        SupportIsAvailableAndEnabledResult,
        roles=["SUPPORT_READ"],
        check_annotations=True,
    )
    async def is_available_and_enabled(self) -> bool:
        """
        Returns whether Proactive Support is available and enabled.
        """
        return await self.is_available() and bool((await self.config()).enabled)

    @api_method(SupportFieldsArgs, SupportFieldsResult, roles=["SUPPORT_READ"], check_annotations=True)
    async def fields(self) -> list[list[str]]:
        """
        Returns list of pairs of field names and field titles for Proactive Support.
        """
        return [
            ["name", "Contact Name"],
            ["title", "Contact Title"],
            ["email", "Contact E-mail"],
            ["phone", "Contact Phone"],
            ["secondary_name", "Secondary Contact Name"],
            ["secondary_title", "Secondary Contact Title"],
            ["secondary_email", "Secondary Contact E-mail"],
            ["secondary_phone", "Secondary Contact Phone"],
        ]

    @api_method(SupportSimilarIssuesArgs, SupportSimilarIssuesResult, roles=["SUPPORT_READ"], check_annotations=True)
    async def similar_issues(self, query: str) -> list[SupportSimilarIssue]:
        """
        Returns a list of similar issues for the given ``query`` from the support knowledge base.
        """
        return await similar_issues(self.context, query)

    @api_method(
        SupportNewTicketArgs,
        SupportNewTicketResult,
        roles=["SUPPORT_WRITE", "READONLY_ADMIN"],
        check_annotations=True,
    )
    @job()
    async def new_ticket(
        self,
        job: Job,
        data: SupportNewTicketEnterprise | SupportNewTicketCommunity,
    ) -> SupportNewTicket:
        """
        Creates a new ticket for support.
        This is done using the support proxy API.
        For TrueNAS Community Edition it will be created on JIRA and for TrueNAS Enterprise on Salesforce.
        """
        return await new_ticket(self.context, job, data)

    @api_method(
        SupportAttachTicketArgs,
        SupportAttachTicketResult,
        roles=["SUPPORT_WRITE", "READONLY_ADMIN"],
        check_annotations=True,
    )
    @job(pipes=["input"])
    def attach_ticket(self, job: Job, data: SupportAttachTicket) -> None:
        """
        Method to attach a file to an existing ticket.
        """
        return attach_ticket(self.context, job, data)

    @api_method(
        SupportAttachTicketMaxSizeArgs,
        SupportAttachTicketMaxSizeResult,
        roles=["SUPPORT_READ"],
        check_annotations=True,
    )
    async def attach_ticket_max_size(self) -> int:
        """
        Returns maximum uploaded file size for :method:`support.attach_ticket`.
        """
        return DEBUG_MAX_SIZE


async def setup(middleware: Middleware) -> None:
    await middleware.call("network.general.register_activity", "support", "Support")
