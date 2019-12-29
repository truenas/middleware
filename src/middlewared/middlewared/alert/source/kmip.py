from middlewared.alert.base import AlertClass, SimpleOneShotAlertClass, AlertCategory, AlertLevel


class KMIPConnectionFailedAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.KMIP
    level = AlertLevel.CRITICAL
    title = 'Failed to Communicate with KMIP Server'
    text = 'Failed to connect to %(server)s KMIP Server: %(error)s.'

    deleted_automatically = False


class KMIPZFSDatasetsSyncFailureAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.KMIP
    level = AlertLevel.CRITICAL
    title = 'Failed to Sync ZFS Keys with KMIP Server'
    text = 'Failed to sync %(datasets)s dataset(s) keys with KMIP Server.'

    deleted_automatically = False


class KMIPSEDDisksSyncFailureAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.KMIP
    level = AlertLevel.CRITICAL
    title = 'Failed to Sync SED Keys with KMIP Server'
    text = 'Failed to sync %(disks)s disk(s) keys with KMIP Server.'

    deleted_automatically = False


class KMIPSEDGlobalPasswordSyncFailureAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.KMIP
    level = AlertLevel.CRITICAL
    title = 'Failed to Sync SED Global Password with KMIP Server'
    text = 'Failed to sync SED global password with KMIP Server.'

    deleted_automatically = False
