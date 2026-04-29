from dataclasses import dataclass
from typing import Any

from middlewared.alert.base import AlertCategory, AlertClassConfig, AlertLevel, OneShotAlertClass


@dataclass(kw_only=True)
class ShareLockedAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SHARING,
        level=AlertLevel.WARNING,
        title="Share Is Unavailable Because It Uses A Locked Dataset",
        text='%(type)s share "%(identifier)s" is unavailable because it uses a locked dataset.',
        deleted_automatically=False,
    )

    type: str
    identifier: str
    id: int

    @classmethod
    def key_from_args(cls, args: Any) -> Any:
        return f'{args["type"]}_{args["id"]}'


@dataclass(kw_only=True)
class TaskLockedAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.TASKS,
        level=AlertLevel.WARNING,
        title="Task Is Unavailable Because It Uses A Locked Dataset",
        text='%(type)s task "%(identifier)s" will not be executed because it uses a locked dataset.',
        deleted_automatically=False,
    )

    type: str
    identifier: str
    id: int

    @classmethod
    def key_from_args(cls, args: Any) -> Any:
        return f'{args["type"]}_{args["id"]}'
