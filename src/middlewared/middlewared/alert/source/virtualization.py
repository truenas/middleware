from dataclasses import dataclass

from middlewared.alert.base import AlertCategory, AlertClassConfig, AlertLevel, OneShotAlertClass


@dataclass(kw_only=True)
class VMAutostartFailedAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.VIRTUALIZATION,
        level=AlertLevel.CRITICAL,
        title="Unable to Automatically Start VMs",
        text=(
            "The following VMs are configured to start automatically but failed to start: %(vms)s. "
            "See /var/log/middlewared.log for the reason each one failed."
        ),
        keys=[],
    )

    vms: str


@dataclass(kw_only=True)
class ContainerAutostartFailedAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.VIRTUALIZATION,
        level=AlertLevel.CRITICAL,
        title="Unable to Automatically Start Containers",
        text=(
            "The following containers are configured to start automatically but failed to start: %(containers)s. "
            "See /var/log/middlewared.log for the reason each one failed."
        ),
        keys=[],
    )

    containers: str
