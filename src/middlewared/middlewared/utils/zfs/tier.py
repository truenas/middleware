from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from middlewared.api.current import ZfsTierEntry

__all__ = ("special_vdev_thresholds",)


def special_vdev_thresholds(config: ZfsTierEntry) -> tuple[int, int]:
    """Return ``(warning, critical)`` SPECIAL-vdev fill thresholds in percent.

    ``critical`` is the lower of the user's configured cap
    (``max_used_percentage``) and the actual ZFS overflow point
    (``100 - special_class_metadata_reserve_pct``) — beyond which the
    kernel stops sending small blocks to SPECIAL and spills them to
    NORMAL, so letting the user set the cap higher than that is
    meaningless.

    ``warning`` sits 10 points below critical with a floor of 50% so the
    warning stays useful even at the minimum cap settings.
    """
    critical = min(
        config.max_used_percentage,
        100 - config.special_class_metadata_reserve_pct,
    )
    warning = max(critical - 10, 50)
    return warning, critical
