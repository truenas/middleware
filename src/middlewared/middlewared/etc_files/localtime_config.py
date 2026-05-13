import contextlib
import os

from middlewared.utils.timezone_choices import (
    FALLBACK_TZ,
    ZONEINFO_DIR,
    timezone_is_available,
)

DEFAULT_TZ = "America/Los_Angeles"


def localtime_configuration(middleware):
    system_config = middleware.call_sync("system.general.config")
    configured_tz = system_config["timezone"] or DEFAULT_TZ

    if timezone_is_available(configured_tz):
        target_tz = configured_tz
        middleware.call_sync(
            "alert.oneshot_delete", "TimezoneNotAvailable", None
        )
    else:
        # If the user's saved zone is one where the symlink does not exist,
        # fall back to UTC and raise an alert so the user sees the
        # divergence between their saved configuration and the running clock.
        target_tz = FALLBACK_TZ
        middleware.logger.warning(
            "Configured timezone %r not found under %s; falling back to %s",
            configured_tz, ZONEINFO_DIR, FALLBACK_TZ,
        )
        middleware.call_sync(
            "alert.oneshot_create",
            "TimezoneNotAvailable",
            {"timezone": configured_tz},
        )

    with contextlib.suppress(OSError):
        os.unlink("/etc/localtime")
    # Relative target matches the systemd/Debian convention written by
    # `timedatectl set-timezone`.
    os.symlink(os.path.join("..", "usr", "share", "zoneinfo", target_tz), "/etc/localtime")


def render(service, middleware):
    localtime_configuration(middleware)
