from datetime import timedelta
import enum
import hashlib
import json
import logging
import os

from middlewared.alert.schedule import IntervalSchedule

__all__ = ["UnavailableException",
           "AlertClass", "OneShotAlertClass", "SimpleOneShotAlertClass", "DismissableAlertClass",
           "AlertCategory", "AlertLevel", "Alert",
           "AlertSource", "FilePresenceAlertSource", "ThreadedAlertSource",
           "AlertService", "ThreadedAlertService", "ProThreadedAlertService",
           "format_alerts", "ellipsis"]

logger = logging.getLogger(__name__)

undefined = object()


class UnavailableException(Exception):
    pass


class AlertClassMeta(type):
    def __init__(cls, name, bases, dct):
        super().__init__(name, bases, dct)

        if cls.__name__ != "AlertClass":
            if not cls.__name__.endswith("AlertClass"):
                raise NameError(f"Invalid alert class name {cls.__name__}")

            cls.name = cls.__name__.replace("AlertClass", "")

            if not cls.exclude_from_list:
                AlertClass.classes.append(cls)
                AlertClass.class_by_name[cls.name] = cls


class AlertClass(metaclass=AlertClassMeta):
    classes = []
    class_by_name = {}

    category = NotImplemented
    level = NotImplemented
    title = NotImplemented
    text = None

    exclude_from_list = False
    hardware = False

    def __init__(self, middleware):
        self.middleware = middleware

    @classmethod
    def format(cls, args):
        if cls.text is None:
            return cls.title

        if args is None:
            return cls.text

        return cls.text % args


class OneShotAlertClass:
    deleted_automatically = True

    async def create(self, args):
        raise NotImplementedError

    async def delete(self, alerts, query):
        raise NotImplementedError


class SimpleOneShotAlertClass(OneShotAlertClass):
    async def create(self, args):
        return Alert(self.__class__, args)

    async def delete(self, alerts, query):
        return list(filter(
            lambda alert: alert.args != query,
            alerts
        ))


class DismissableAlertClass:
    async def dismiss(self, alerts, alert):
        raise NotImplementedError


class AlertCategory(enum.Enum):
    CERTIFICATES = "CERTIFICATES"
    DIRECTORY_SERVICE = "DIRECTORY_SERVICE"
    HA = "HA"
    HARDWARE = "HARDWARE"
    NETWORK = "NETWORK"
    REPORTING = "REPORTING"
    SHARING = "SHARING"
    STORAGE = "STORAGE"
    SYSTEM = "SYSTEM"
    TASKS = "TASKS"
    UPS = "UPS"


alert_category_names = {
    AlertCategory.CERTIFICATES: "Certificates",
    AlertCategory.DIRECTORY_SERVICE: "Directory Service",
    AlertCategory.HA: "High-Availability",
    AlertCategory.HARDWARE: "Hardware",
    AlertCategory.NETWORK: "Network",
    AlertCategory.REPORTING: "Reporting",
    AlertCategory.SHARING: "Sharing",
    AlertCategory.STORAGE: "Storage",
    AlertCategory.SYSTEM: "System",
    AlertCategory.TASKS: "Tasks",
    AlertCategory.UPS: "UPS",
}


class AlertLevel(enum.Enum):
    INFO = 1
    NOTICE = 2
    WARNING = 3
    ERROR = 4
    CRITICAL = 5
    ALERT = 6
    EMERGENCY = 7


class Alert:
    def __init__(self, klass, args=None, key=undefined, datetime=None, node=None, dismissed=None, mail=None,
                 _uuid=None, _source=None, _key=None, _text=None):
        self.uuid = _uuid
        self.source = _source
        self.klass = klass
        self.args = args

        self.node = node
        if _key is None:
            if key is undefined:
                key = args
            self.key = json.dumps(key, sort_keys=True)
        else:
            self.key = _key
        self.datetime = datetime
        self.dismissed = dismissed
        self.mail = mail

        self.text = _text or self.klass.text or self.klass.title

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __repr__(self):
        return repr(self.__dict__)

    @property
    def formatted(self):
        try:
            return self.klass.format(self.args)
        except Exception:
            logger.debug("Alert class %r was unable to format args %r, falling back to default formatter",
                         self.klass, self.args, exc_info=True)

            if self.args:
                try:
                    return self.text % (tuple(self.args) if isinstance(self.args, list) else self.args)
                except Exception:
                    logger.error("Error formatting alert: %r, %r", self.text, self.args, exc_info=True)

            return self.text


class AlertSource:
    schedule = IntervalSchedule(timedelta())

    run_on_backup_node = True

    def __init__(self, middleware):
        self.middleware = middleware

    @property
    def name(self):
        return self.__class__.__name__.replace("AlertSource", "")

    async def check(self):
        raise NotImplementedError


class FilePresenceAlertSource(AlertSource):
    path = NotImplemented
    klass = NotImplemented

    async def check(self):
        if os.path.exists(self.path):
            return Alert(self.klass)


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

    def _alert_id(self, alert):
        return hashlib.sha256(json.dumps([alert.source, alert.key]).encode("utf-8")).hexdigest()

    async def _format_alerts(self, alerts, gone_alerts, new_alerts):
        product_name = await self.middleware.call("system.product_name")
        hostname = (await self.middleware.call("system.info"))["hostname"]
        return format_alerts(product_name, hostname, alerts, gone_alerts, new_alerts)


class ThreadedAlertService(AlertService):
    async def send(self, alerts, gone_alerts, new_alerts):
        return await self.middleware.run_in_thread(self.send_sync, alerts, gone_alerts, new_alerts)

    def send_sync(self, alerts, gone_alerts, new_alerts):
        raise NotImplementedError

    def _format_alerts(self, alerts, gone_alerts, new_alerts):
        product_name = self.middleware.call_sync("system.product_name")
        hostname = self.middleware.call_sync("system.info")["hostname"]
        return format_alerts(product_name, hostname, alerts, gone_alerts, new_alerts)


class ProThreadedAlertService(ThreadedAlertService):
    def send_sync(self, alerts, gone_alerts, new_alerts):
        exc = None

        for alert in gone_alerts:
            try:
                self.delete_alert(alert)
            except Exception as e:
                self.logger.warning("An exception occurred while deleting alert", exc_info=True)
                exc = e

        for alert in new_alerts:
            try:
                self.create_alert(alert)
            except Exception as e:
                self.logger.warning("An exception occurred while creating alert", exc_info=True)
                exc = e

        if exc is not None:
            raise exc

    def create_alert(self, alert):
        raise NotImplementedError

    def delete_alert(self, alert):
        raise NotImplementedError


def format_alerts(product_name, hostname, alerts, gone_alerts, new_alerts):
    text = f"{product_name} @ {hostname}\n\n"

    if new_alerts:
        text += "New alerts:\n" + "".join(["* %s\n" % format_alert(alert) for alert in new_alerts]) + "\n"

    if gone_alerts:
        text += "Gone alerts:\n" + "".join(["* %s\n" % format_alert(alert) for alert in gone_alerts]) + "\n"

    if alerts:
        text += "Current alerts:\n" + "".join(["* %s\n" % format_alert(alert) for alert in alerts]) + "\n"

    return text


def format_alert(alert):
    return alert.formatted + (f" (on node {alert.node})" if alert.node != "A" else "")


def ellipsis(s, l):
    if len(s) <= l:
        return s

    return s[:(l - 1)] + "…"
