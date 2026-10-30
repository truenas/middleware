from __future__ import annotations

from typing import TYPE_CHECKING, Any

from middlewared.alert.source.license_features import LicenseFeaturesAlert
from middlewared.utils.entitlements import POLICY, check_entitlement, get_facts

if TYPE_CHECKING:
    import asyncio

    from middlewared.common.license_delegate import LicenseDelegate
    from middlewared.main import Middleware
    from middlewared.service import ServiceContext

GRACE_KEY = "truenas.entitlements.grace"  # VOLATILE cache; sorted list of the features still served in grace


def entitled_now() -> frozenset[str]:  # sync: blocking daemon read
    facts = get_facts()
    return frozenset(k for k in POLICY if check_entitlement(k, facts).entitled)


def grace_compute(role: str, from_peer: bool) -> bool:
    # a BACKUP runs no workloads to probe; a non-MASTER handed the peer's upload holds the active's settings
    return role == "MASTER" or (role != "BACKUP" and not from_peer)


def register(delegates: dict[str, LicenseDelegate], delegate: LicenseDelegate) -> None:
    if delegate.feature not in POLICY or delegate.feature in delegates:
        raise ValueError(f"{delegate.feature}: not a policy feature, or already registered")
    delegates[delegate.feature] = delegate


async def grace_record(context: ServiceContext) -> frozenset[str]:
    try:
        return frozenset(await context.middleware.call("cache.get", GRACE_KEY))
    except KeyError:
        return frozenset()


def serving(context: ServiceContext, feature: str) -> bool:  # sync: renderers call it from threads
    if context.call_sync2(context.s.truenas.entitlements.check, feature).entitled:
        return True
    try:
        return feature in context.middleware.call_sync("cache.get", GRACE_KEY)
    except KeyError:
        return False


async def _in_use(context: ServiceContext, delegate: LicenseDelegate) -> bool:
    try:
        return await delegate.in_use()
    except Exception:
        context.logger.error("%s: in_use failed; keeping the feature served", delegate.feature, exc_info=True)
        return True


async def _write(context: ServiceContext, drop: frozenset[str], add: frozenset[str]) -> bool:
    # the caller holds the record's lock
    old = await grace_record(context)
    new = (old - drop) | add
    if new == old:
        return False
    await context.middleware.call("cache.put", GRACE_KEY, sorted(new))
    return True


async def _push(context: ServiceContext) -> None:
    await context.middleware.call("failover.sync_keys_to_remote_node")


async def license_changed(
    context: ServiceContext,
    delegates: dict[str, LicenseDelegate],
    lock: asyncio.Lock,
    before: frozenset[str],
    after: frozenset[str],
    compute: bool,
) -> None:
    if not compute:
        return  # the serving node computes; this node gets its record by key sync
    try:
        # probes under the lock: a cut that lands meanwhile waits for this write instead of being undone by it
        async with lock:
            used = frozenset([f for f in before - after if (d := delegates.get(f)) and await _in_use(context, d)])
            # entitled features never stay in the record; features unentitled before and after keep their entry
            changed = await _write(context, after, used)
        if changed:
            await _push(context)
        context.create_task(_apply_grants(context, delegates, after - before))
        await refresh_alert(context, delegates, lock, after)
    except Exception:
        context.logger.error("license change: grace update failed", exc_info=True)


async def _apply_grants(
    context: ServiceContext, delegates: dict[str, LicenseDelegate], granted: frozenset[str]
) -> None:
    for f in granted:
        if (d := delegates.get(f)) is not None:
            try:
                await d.on_grant()
            except Exception:
                context.logger.error("%s: on_grant failed", f, exc_info=True)


async def cut_service(
    context: ServiceContext, delegates: dict[str, LicenseDelegate], lock: asyncio.Lock, service: str
) -> None:
    try:
        cut = frozenset(f for f, d in delegates.items() if service in d.services)
        if not cut & await grace_record(context):
            return  # read before the status so an ordinary stop costs nothing
        if await context.middleware.call("failover.status") == "BACKUP":
            return  # the MASTER's record is the pair's record
        async with lock:
            changed = await _write(context, cut, frozenset())
        if changed:
            # not awaited: an operator's service action must not wait on the peer
            context.create_task(_push(context))
            await refresh_alert(context, delegates, lock, None)
    except Exception:
        context.logger.error("%s: grace cut failed", service, exc_info=True)


async def refresh_alert(
    context: ServiceContext,
    delegates: dict[str, LicenseDelegate],
    lock: asyncio.Lock,
    entitled: frozenset[str] | None,
) -> None:
    try:
        if entitled is None:
            entitled = await context.to_thread(entitled_now)
        # under the record's lock, so a rewrite cannot read a record that a later-submitted rewrite has replaced
        async with lock:
            record = await grace_record(context)
            lines: list[str] = []
            for d in delegates.values():
                if d.feature in entitled:
                    continue
                try:
                    lines.extend(await d.alert_lines(d.feature in record))
                except Exception:
                    context.logger.error("%s: alert_lines failed", d.feature, exc_info=True)
            text = "\n".join(lines)
            if text:
                await context.call2(context.s.alert.oneshot_create, LicenseFeaturesAlert(lines=text))
            await context.call2(context.s.alert.oneshot_delete, "LicenseFeatures", text or None)
    except Exception:
        context.logger.error("license alert: refresh failed", exc_info=True)


async def _on_system_ready(middleware: Middleware, event_type: str, args: Any) -> None:
    if await middleware.call("failover.licensed"):
        return  # on HA a takeover clears one-shot alerts, and a standby keeps none of its own
    await middleware.call2(middleware.services.truenas.entitlements.refresh_alert)


async def setup(middleware: Middleware) -> None:
    middleware.event_subscribe("system.ready", _on_system_ready)
