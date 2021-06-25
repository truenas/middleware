from datetime import timedelta
import enum
import json
import logging
import os

import html2text

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
    products = ("CORE", "ENTERPRISE", "SCALE", "SCALE_ENTERPRISE")
    hardware = False

    def __init__(self, middleware):
        self.middleware = middleware

    @classmethod
    def format(cls, args):
        if cls.text is None:
            return cls.title

        if args is None:
            return cls.text

        return cls.text % (tuple(args) if isinstance(args, list) else args)


class OneShotAlertClass:
    deleted_automatically = True
    expires_after = None

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
    APPLICATIONS = "APPLICATIONS"
    CERTIFICATES = "CERTIFICATES"
    DIRECTORY_SERVICE = "DIRECTORY_SERVICE"
    HA = "HA"
    HARDWARE = "HARDWARE"
    KMIP = "KMIP"
    PLUGINS = "PLUGINS"
    NETWORK = "NETWORK"
    REPORTING = "REPORTING"
    SHARING = "SHARING"
    STORAGE = "STORAGE"
    SYSTEM = "SYSTEM"
    TASKS = "TASKS"
    UPS = "UPS"


alert_category_names = {
    AlertCategory.APPLICATIONS: "Applications",
    AlertCategory.CERTIFICATES: "Certificates",
    AlertCategory.DIRECTORY_SERVICE: "Directory Service",
    AlertCategory.HA: "High-Availability",
    AlertCategory.HARDWARE: "Hardware",
    AlertCategory.KMIP: "Key Management Interoperability Protocol (KMIP)",
    AlertCategory.PLUGINS: "Plugins",
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
    def __init__(self, klass, args=None, key=undefined, datetime=None, last_occurrence=None, node=None, dismissed=None,
                 mail=None, _uuid=None, _source=None, _key=None, _text=None):
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
        self.last_occurrence = last_occurrence or datetime
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

    products = ("CORE", "ENTERPRISE", "SCALE", "SCALE_ENTERPRISE")
    failover_related = False
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

    html = False

    def __init__(self, middleware, attributes):
        self.middleware = middleware
        self.attributes = attributes

        self.logger = logging.getLogger(self.__class__.__name__)

        # If we remove some attributes, it should not be an error if they are still left in the database
        schema = self.schema.copy()
        schema.additional_attrs = True
        # Set defaults for new attributes
        self.attributes = schema.clean(self.attributes)

    @classmethod
    def name(cls):
        return cls.__name__.replace("AlertService", "")

    @classmethod
    def validate(cls, attributes):
        cls.schema.validate(attributes)

    async def send(self, alerts, gone_alerts, new_alerts):
        raise NotImplementedError

    async def _format_alerts(self, alerts, gone_alerts, new_alerts):
        product_name = await self.middleware.call("system.product_name")
        hostname = await self.middleware.call('system.hostname')
        if await self.middleware.call("system.is_enterprise"):
            node_map = await self.middleware.call("alert.node_map")
        else:
            node_map = None

        html = format_alerts(product_name, hostname, node_map, alerts, gone_alerts, new_alerts)

        if self.html:
            return html

        return html2text.html2text(html).rstrip()


class ThreadedAlertService(AlertService):
    async def send(self, alerts, gone_alerts, new_alerts):
        return await self.middleware.run_in_thread(self.send_sync, alerts, gone_alerts, new_alerts)

    def send_sync(self, alerts, gone_alerts, new_alerts):
        raise NotImplementedError

    def _format_alerts(self, alerts, gone_alerts, new_alerts):
        product_name = self.middleware.call_sync("system.product_name")
        hostname = await self.middleware.call('system.hostname')
        if self.middleware.call_sync("system.is_enterprise"):
            node_map = self.middleware.call_sync("alert.node_map")
        else:
            node_map = None
        return format_alerts(product_name, hostname, node_map, alerts, gone_alerts, new_alerts)


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


def format_alerts(product_name, hostname, node_map, alerts, gone_alerts, new_alerts):
    text = f"{product_name} @ {hostname}<br><br>"

    if len(alerts) == 1 and len(gone_alerts) == 0 and len(new_alerts) == 1 and new_alerts[0].klass.name == "Test":
        return text + "This is a test alert"

    if new_alerts:
        if len(gone_alerts) == 1:
            text += "New alert"
        else:
            text += "New alerts"
        text += ":\n<ul>" + "".join([
            "<li>%s</li>\n" % format_alert(alert, node_map)
            for alert in new_alerts
        ]) + "</ul>"

    if gone_alerts:
        if len(gone_alerts) == 1:
            text += "The following alert has been cleared"
        else:
            text += "These alerts have been cleared"
        text += ":\n<ul>" + "".join([
            "<li>%s</li>\n" % format_alert(alert, node_map)
            for alert in gone_alerts
        ]) + "</ul>\n"

    if alerts:
        text += "Current alerts:\n<ul>" + "".join([
            "<li>%s</li>\n" % format_alert(alert, node_map)
            for alert in alerts
        ]) + "</ul>\n"

    return text


def format_alert(alert, node_map):
    return (f"{node_map[alert.node]} - " if node_map else "") + alert.formatted


def ellipsis(s, l):
    if len(s) <= l:
        return s

    return s[:(l - 1)] + "…"
