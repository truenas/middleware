from __future__ import annotations

from typing import Any

from middlewared.api.current import TruecommandStatus
from middlewared.service import ServiceContext

# In the database we save 3 states, CONNECTED/DISABLED/FAILED. Here we hold the status
# we report to the user, which also accounts for the live wireguard connection health.
STATUS = TruecommandStatus.DISABLED

HEALTH_ALERTS = frozenset({"TruecommandConnectionHealth", "TruecommandContainerHealth"})
NON_HEALTH_ALERTS = frozenset({"TruecommandConnectionDisabled", "TruecommandConnectionPending"})


def get_status() -> TruecommandStatus:
    return STATUS


async def set_status(context: ServiceContext, new_status: str) -> None:
    global STATUS
    assert new_status in TruecommandStatus.__members__
    STATUS = TruecommandStatus(new_status)
    context.middleware.send_event("truecommand.config", "CHANGED", fields=await event_config(context))


async def event_config(context: ServiceContext) -> dict[str, Any]:
    config = await context.call2(context.s.truecommand.config)
    return config.model_dump(exclude={"api_key"})


async def dismiss_alerts(
    context: ServiceContext,
    dismiss_health: bool = False,
    dismiss_health_only: bool = False,
) -> None:
    # We do not dismiss health by default because it's possible that the key has not been revoked
    # and it's just that TC has not connected to TN in 30 minutes, so we only should dismiss it when
    # we update TC service or the health is okay now with the service running or when service is not running
    if dismiss_health_only:
        to_dismiss_alerts = HEALTH_ALERTS
    else:
        to_dismiss_alerts = HEALTH_ALERTS | NON_HEALTH_ALERTS if dismiss_health else NON_HEALTH_ALERTS
    for klass in to_dismiss_alerts:
        await context.call2(context.s.alert.oneshot_delete, klass, None)
