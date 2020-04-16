# Copyright (c) 2015 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

from middlewared.alert.base import (
    Alert, AlertClass, SimpleOneShotAlertClass, AlertCategory, AlertLevel, OneShotAlertClass
)


class FailoverSyncFailedAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = "Automatic Sync to Peer Failed"
    text = (
        "Failed to sync configuration information to standby storage "
        "controller. Use Sync to Peer on the System/Failover page to "
        "perform a manual sync."
    )

    products = ("ENTERPRISE",)


class FailoverKeysSyncFailedAlertClass(AlertClass, SimpleOneShotAlertClass):
    deleted_automatically = False

    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = "Syncing Encryption Keys to Peer Failed"
    text = (
        "The automatic synchronization of encryption passphrases with the standby "
        "controller has failed. Please go to System > Failover and manually sync to peer."
    )

    products = ("ENTERPRISE",)


class FailoverKMIPKeysSyncFailedAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False

    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = "Syncing KMIP Keys to Peer Failed"
    text = (
        "The automatic synchronization of KMIP keys with the standby "
        "controller has failed due to %(error)s. Please go to System > Failover and manually sync to peer."
    )

    products = ("ENTERPRISE",)

    async def create(self, args):
        return Alert(FailoverKMIPKeysSyncFailedAlertClass, args)

    async def delete(self, alerts, query):
        return []
