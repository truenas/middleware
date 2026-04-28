# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from dataclasses import dataclass

from middlewared.alert.base import AlertCategory, AlertClassConfig, AlertLevel, OneShotAlertClass
from middlewared.utils import ProductType


@dataclass(kw_only=True)
class FailoverSyncFailedAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.HA,
        level=AlertLevel.CRITICAL,
        title="Automatic Sync to Peer Failed",
        text=(
            "Tried for %(mins)d minutes to sync configuration information to "
            "the standby storage controller but failed. Use Sync to Peer on the "
            "System/Failover page to try and perform a manual sync."
        ),
        products=(ProductType.ENTERPRISE,),
        keys=[],
    )

    mins: int


class FailoverKeysSyncFailedAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.HA,
        level=AlertLevel.CRITICAL,
        title="Syncing Encryption Keys to Peer Failed",
        text=(
            "The automatic synchronization of encryption passphrases with the standby "
            "controller has failed. Please go to System > Failover and manually sync to peer."
        ),
        products=(ProductType.ENTERPRISE,),
        deleted_automatically=False,
    )


@dataclass(kw_only=True)
class FailoverKMIPKeysSyncFailedAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.HA,
        level=AlertLevel.CRITICAL,
        title="Syncing KMIP Keys to Peer Failed",
        text=(
            "The automatic synchronization of KMIP keys with the standby "
            "controller has failed due to %(error)s. Please go to System > Failover and manually sync to peer."
        ),
        products=(ProductType.ENTERPRISE,),
        deleted_automatically=False,
        keys=[],
    )

    error: str
