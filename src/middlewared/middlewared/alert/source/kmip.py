# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from middlewared.alert.base import AlertClass, OneShotAlertClass, AlertCategory, AlertLevel


class KMIPConnectionFailedAlertClass(AlertClass, OneShotAlertClass):
    category = AlertCategory.KMIP
    level = AlertLevel.CRITICAL
    title = 'Failed to Communicate with KMIP Server'
    text = 'Failed to connect to %(server)s KMIP Server: %(error)s.'

    deleted_automatically = False


class KMIPZFSDatasetsSyncFailureAlertClass(AlertClass, OneShotAlertClass):
    category = AlertCategory.KMIP
    level = AlertLevel.CRITICAL
    title = 'Failed to Sync ZFS Keys with KMIP Server'
    text = 'Failed to sync %(datasets)s dataset(s) keys with KMIP Server.'

    deleted_automatically = False


class KMIPSEDDisksSyncFailureAlertClass(AlertClass, OneShotAlertClass):
    category = AlertCategory.KMIP
    level = AlertLevel.CRITICAL
    title = 'Failed to Sync SED Keys with KMIP Server'
    text = 'Failed to sync %(disks)s disk(s) keys with KMIP Server.'

    deleted_automatically = False


class KMIPSEDGlobalPasswordSyncFailureAlertClass(AlertClass, OneShotAlertClass):
    category = AlertCategory.KMIP
    level = AlertLevel.CRITICAL
    title = 'Failed to Sync SED Global Password with KMIP Server'
    text = 'Failed to sync SED global password with KMIP Server.'

    deleted_automatically = False
