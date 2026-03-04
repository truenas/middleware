from dataclasses import dataclass

from middlewared.alert.base import AlertClass, AlertClassConfig, AlertCategory, AlertLevel, OneShotAlertClass


@dataclass(kw_only=True)
class RsyncSuccessAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.TASKS,
        level=AlertLevel.INFO,
        title='Rsync Task Succeeded',
        text='Rsync "%(direction)s" task for "%(path)s" succeeded.',
        deleted_automatically=False,
    )

    direction: str
    path: str
    id: int

    @classmethod
    def key(cls, args):
        return args['id']


@dataclass(kw_only=True)
class RsyncFailedAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.TASKS,
        level=AlertLevel.CRITICAL,
        title='Rsync Task Failed',
        text='Rsync "%(direction)s" task for "%(path)s" failed.',
        deleted_automatically=False,
    )

    direction: str
    path: str
    id: int

    @classmethod
    def key(cls, args):
        return args['id']
