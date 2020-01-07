# Copyright (c) 2015 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

from middlewared.alert.base import AlertClass, SimpleOneShotAlertClass, AlertCategory, AlertLevel


class FailoverSyncFailedAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.CRITICAL
    title = "Automatic Sync to Peer Failed"
    text = (
        "Failed to sync configuration information to standby storage "
        "controller. Use Sync to Peer on the System/Failover page to "
        "perform a manual sync."
    )

    products = ("ENTERPRISE",)
