from dataclasses import dataclass
from typing import Any

from middlewared.alert.base import AlertCategory, AlertClassConfig, AlertLevel, OneShotAlertClass

URL = "https://www.truenas.com/docs/scale/scaledeprecatedfeatures/"


@dataclass(kw_only=True)
class DeprecatedServiceAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SHARING,
        level=AlertLevel.WARNING,
        title="Deprecated Service is Running",
        text=(
            "The following active service is deprecated %(service)s. "
            "This service is scheduled for removal in a future version of SCALE. "
            f"Before upgrading, please check {URL} to confirm whether or not "
            "the service has been removed in the next version of SCALE."
        ),
    )

    service: str

    @classmethod
    def key_from_args(cls, args: Any) -> Any:
        return args["service"]
