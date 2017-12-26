from datetime import timedelta
import enum
import logging
import os

__all__ = ["AlertLevel", "Alert", "AlertSource", "FilePresenceAlertSource", "ThreadedAlertSource",
           "AlertService", "ThreadedAlertService",
           "format_alerts"]

logger = logging.getLogger(__name__)

undefined = object()


class AlertLevel(enum.Enum):
    INFO = 20
    WARNING = 30
    CRITICAL = 50


class Alert:
    def __init__(self, title=None, args=None, source=None, key=undefined, datetime=None, level=None, dismissed=None):
        self.title = title
        self.args = args

        self.source = source
        if key is not undefined:
            self.key = key
        else:
            self.key = self.formatted
        self.datetime = datetime
        self.level = level
        self.dismissed = dismissed

    def __repr__(self):
        return repr(self.__dict__)

    @property
    def level_name(self):
        return AlertLevel(self.level).name

    @property
    def formatted(self):
        if self.args:
            try:
                return self.title % self.args
            except Exception:
                logger.error("Error formatting alert: %r, %r", self.title, self.args, exc_info=True)

        return self.title


class AlertSource:
    level = NotImplemented
    title = NotImplemented

    hardware = False

    onetime = False
    interval = timedelta()

    def __init__(self, middleware):
        self.middleware = middleware

    @property
    def name(self):
        return self.__class__.__name__.replace("AlertSource", "")

    async def check(self):
        raise NotImplementedError


class FilePresenceAlertSource(AlertSource):
    path = NotImplementedError

    async def check(self):
        if os.path.exists(self.path):
            return Alert()


class ThreadedAlertSource(AlertSource):
    async def check(self):
        return await self.middleware.run_in_thread(self.check_sync)

    def check_sync(self):
        raise NotImplementedError


class AlertService:
    title = NotImplementedError

    schema = NotImplementedError

    def __init__(self, middleware, attributes):
        self.middleware = middleware
        self.attributes = attributes

        self.logger = logging.getLogger(self.__class__.__name__)

    @classmethod
    def name(cls):
        return cls.__name__.replace("AlertService", "")

    @classmethod
    def validate(cls, attributes):
        cls.schema.validate(attributes)

    async def send(self, alerts, gone_alerts, new_alerts):
        raise NotImplementedError


class ThreadedAlertService(AlertService):
    async def send(self, alerts, gone_alerts, new_alerts):
        return await self.middleware.run_in_thread(self.send_sync, alerts, gone_alerts, new_alerts)

    def send_sync(self, alerts, gone_alerts, new_alerts):
        raise NotImplementedError


def format_alerts(alerts, gone_alerts, new_alerts):
    text = ""

    if new_alerts:
        text += "New alerts:\n" + "".join([f"* {alert.formatted}\n" for alert in new_alerts]) + "\n"

    if gone_alerts:
        text += "Gone alerts:\n" + "".join([f"* {alert.formatted}\n" for alert in gone_alerts]) + "\n"

    if alerts:
        text += "Alerts:\n" + "".join([f"* {alert.formatted}\n" for alert in new_alerts]) + "\n"

    return text
