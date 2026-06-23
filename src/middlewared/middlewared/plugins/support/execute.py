from __future__ import annotations

import asyncio
import errno
import json
import shutil
import tempfile
import time
from typing import TYPE_CHECKING, Any

import aiohttp
import requests

from middlewared.api.current import (
    SupportAttachTicket,
    SupportNewTicket,
    SupportNewTicketCommunity,
    SupportNewTicketEnterprise,
    SupportSimilarIssue,
)
from middlewared.pipe import InputPipes, Pipes
from middlewared.plugins.system.utils import DEBUG_MAX_SIZE
from middlewared.service import CallError
from middlewared.utils import sw_version
from middlewared.utils.network import INTERNET_TIMEOUT

if TYPE_CHECKING:
    from middlewared.job import Job
    from middlewared.service import ServiceContext

ADDRESS = "support-proxy.truenas.com"


async def post(url: str, data: str, timeout: int = INTERNET_TIMEOUT) -> Any:
    try:
        async with asyncio.timeout(timeout):
            async with aiohttp.ClientSession(
                raise_for_status=True,
                trust_env=True,
            ) as session:
                req = await session.post(url, headers={"Content-Type": "application/json"}, data=data)
    except asyncio.TimeoutError:
        raise CallError("Connection timed out", errno.ETIMEDOUT)
    except aiohttp.ClientResponseError as e:
        raise CallError(f"Invalid server response: {e}", errno.EBADMSG)

    try:
        return await req.json()
    except aiohttp.client_exceptions.ContentTypeError:
        raise CallError(f"Invalid server response: {req.status}", errno.EBADMSG)


async def similar_issues(context: ServiceContext, query: str) -> list[SupportSimilarIssue]:
    await context.middleware.call("network.general.will_perform_activity", "support")

    data = await post(
        f"https://{ADDRESS}/freenas/api/v1.0/similar_issues",
        data=json.dumps({"query": query}),
    )

    if "error" in data:
        raise CallError(data["message"], errno.EINVAL)

    return [SupportSimilarIssue(**issue) for issue in data]


async def new_ticket(
    context: ServiceContext,
    job: Job,
    data: SupportNewTicketEnterprise | SupportNewTicketCommunity,
) -> SupportNewTicket:
    vendor = await context.call2(context.s.system.vendor.name)
    if vendor:
        raise CallError(f"Support is not available for this product ({vendor})", errno.EINVAL)

    await context.middleware.call("network.general.will_perform_activity", "support")

    job.set_progress(1, "Gathering data")

    sw_name = "freenas" if not await context.middleware.call("system.is_enterprise") else "truenas"

    payload = data.model_dump(context={"expose_secrets": True})

    required_attrs: tuple[str, ...]
    if sw_name == "freenas":
        required_attrs = ("type", "token")
    else:
        required_attrs = ("category", "phone", "name", "email", "criticality", "environment")
        payload["serial"] = (await context.middleware.call("system.dmidecode_info"))["system-serial-number"]
        license_ = await context.call2(context.s.truenas.license.info_private)
        if license_:
            payload["license_id"] = license_.id

    for attr in required_attrs:
        if attr not in payload:
            raise CallError(f"{attr} is required", errno.EINVAL)

    payload["version"] = sw_version()
    debug = payload.pop("attach_debug")

    type_ = payload.get("type")
    if type_:
        payload["type"] = type_.lower()

    job.set_progress(20, "Submitting ticket")

    result = await post(
        f"https://{ADDRESS}/{sw_name}/api/v1.0/ticket",
        data=json.dumps(payload),
    )
    if result["error"]:
        raise CallError(result["message"], errno.EINVAL)

    ticket = result.get("ticketnum")
    url = result.get("message")
    if not ticket:
        raise CallError("New ticket number was not informed", errno.EINVAL)
    job.set_progress(50, f"Ticket created: {ticket}", extra={"ticket": ticket})

    has_debug = False
    debug_attach_error = None
    if debug:
        job.set_progress(60, "Generating debug file")

        debug_job = await context.middleware.call(
            "system.debug",
            pipes=Pipes(output=context.middleware.pipe()),
        )

        if await context.middleware.call("failover.licensed"):
            debug_name = "debug-{}.tar".format(time.strftime("%Y%m%d%H%M%S"))
        else:
            debug_name = "debug-{}-{}.txz".format(
                (await context.middleware.call("system.hostname")).split(".")[0],
                time.strftime("%Y%m%d%H%M%S"),
            )

        with tempfile.NamedTemporaryFile("w+b") as f:

            def copy1() -> None:
                nonlocal has_debug, debug_attach_error
                try:
                    rbytes = 0
                    while True:
                        r = debug_job.pipes.output.r.read(1048576)
                        if r == b"":
                            break

                        rbytes += len(r)
                        if rbytes > DEBUG_MAX_SIZE * 1048576:
                            debug_attach_error = (
                                f"The debug file exceeds the {DEBUG_MAX_SIZE}MiB size limit. "
                                f"Please generate and attach a debug manually."
                            )
                            context.logger.warning(
                                "Debug exceeded %dMiB limit for ticket %s; not attaching.",
                                DEBUG_MAX_SIZE,
                                ticket,
                            )
                            return

                        f.write(r)

                    f.seek(0)
                    has_debug = True
                finally:
                    debug_job.pipes.output.r.read()

            await context.to_thread(copy1)
            await debug_job.wait()
            if debug_job.error:
                has_debug = False
                if not debug_attach_error:
                    debug_attach_error = f"Failed to generate debug: {debug_job.error}"
                context.logger.warning("Debug generation failed for ticket %s: %s", ticket, debug_job.error)

            if has_debug:
                job.set_progress(80, "Attaching debug file")

                token = payload.get("token")
                if token is not None:
                    attach = SupportAttachTicket(ticket=ticket, filename=debug_name, token=token)
                else:
                    attach = SupportAttachTicket(ticket=ticket, filename=debug_name)
                tjob: Job[None] = await context.middleware.call2(
                    context.s.support.attach_ticket,
                    attach,
                    pipes=Pipes(inputs=InputPipes(context.middleware.pipe())),
                )

                def copy2() -> None:
                    try:
                        shutil.copyfileobj(f, tjob.pipes.input.w)
                    finally:
                        tjob.pipes.input.w.close()

                await context.to_thread(copy2)
                await tjob.wait()
                if tjob.error:
                    has_debug = False
                    debug_attach_error = str(tjob.error)
    else:
        job.set_progress(100)

    return SupportNewTicket(ticket=ticket, url=url, has_debug=has_debug, debug_attach_error=debug_attach_error)


def attach_ticket(context: ServiceContext, job: Job, data: SupportAttachTicket) -> None:
    context.middleware.call_sync("network.general.will_perform_activity", "support")

    sw_name = "freenas" if not context.middleware.call_sync("system.is_enterprise") else "truenas"

    payload = data.model_dump(context={"expose_secrets": True})
    payload["ticketnum"] = payload.pop("ticket")
    filename = payload.pop("filename")

    try:
        r = requests.post(
            f"https://{ADDRESS}/{sw_name}/api/v1.0/ticket/attachment",
            data=payload,
            timeout=300,
            files={"file": (filename, job.pipes.input.r)},
        )
    except requests.ConnectionError as e:
        raise CallError(f"Connection error {e}", errno.EBADF)
    except requests.Timeout:
        raise CallError("Connection time out", errno.ETIMEDOUT)

    if r.status_code == 413:
        raise CallError("Uploaded file is too large", errno.EFBIG)

    try:
        response = r.json()
    except ValueError:
        context.logger.debug("Failed to decode ticket attachment response: %s", r.text)
        raise CallError(f"Invalid server response: {r.status_code}", errno.EBADMSG)

    if response["error"]:
        raise CallError(response["message"], errno.EINVAL)
