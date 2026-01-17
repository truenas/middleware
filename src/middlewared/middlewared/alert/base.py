from __future__ import annotations

from datetime import datetime, timedelta
import enum
import json
import logging
from typing import Any, TypeAlias

import html2text

from middlewared.alert.schedule import IntervalSchedule
from middlewared.utils import ProductName, ProductType
from middlewared.utils.lang import undefined
from middlewared.utils.service.call_mixin import CallMixin

__all__ = [
    "UnavailableException", "AlertClass", "OneShotAlertClass", "SimpleOneShotAlertClass", "DismissableAlertClass",
    "AlertCategory", "AlertLevel", "Alert", "AlertSource", "ThreadedAlertSource", "AlertService",
    "ThreadedAlertService", "ProThreadedAlertService", "format_alerts", "ellipsis", "alert_category_names",
]

logger = logging.getLogger(__name__)


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


class AlertClass(CallMixin, metaclass=AlertClassMeta):
    """
    Alert class: a description of a specific type of issue that can exist in the system.

    :cvar category: `AlertCategory` value

    :cvar level: Default `AlertLevel` value (alert level can be later changed by user)

    :cvar title: Short description of the alert class (e.g. "An SSL certificate is expiring")

    :cvar text: Format string for the alert class instance (e.g. "%(name)s SSL certificate is expiring")

    :cvar exclude_from_list: Set this to `true` to exclude the alert from the UI configuration. For example, you might
        want to hide some rare legacy hardware-specific alert. It will still be sent if it occurs, but users won't be
        able to disable it or change its level.

    :cvar products: A list of `system.product_type` return values on which alerts of this class can be emitted.

    :cvar proactive_support: Set this to `true` if, upon creation of the alert, a support ticket should be open for the
        systems that have a corresponding support license.

    :cvar proactive_support_notify_gone: Set this to `true` if, upon removal of the alert, a support ticket should be
        open for the systems that have a corresponding support license.
    """

    classes = []
    class_by_name = {}

    category: AlertCategory = NotImplemented
    level: AlertLevel = NotImplemented
    title: str = NotImplemented
    text: str | None = None

    exclude_from_list = False
    products = (ProductType.COMMUNITY_EDITION, ProductType.ENTERPRISE)
    proactive_support = False
    proactive_support_notify_gone = False

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
    """
    One-shot alert mixin: add this to `AlertClass` superclass list to the alerts that are created not by an
    `AlertSource` but using `alert.oneshot_create` API method.

    :cvar deleted_automatically: Set this to `false` if there is no one to call `alert.oneshot_delete` when the alert
        situation is resolved. In that case, the alert will be deleted when the user dismisses it.

    :cvar expires_after: Lifetime for the alert.
    """

    deleted_automatically = True
    expires_after = None

    async def create(self, args):
        """
        Returns an `Alert` instance created using `args` that were passed to `alert.oneshot_create`.

        :param args: free-form data that was passed  to `alert.oneshot_create`.
        :return: an `Alert` instance.
        """
        raise NotImplementedError

    async def delete(self, alerts, query):
        """
        Returns only those `alerts` that do not match `query` that was passed to `alert.oneshot_delete`.

        :param alerts: all the alerts of this class.
        :param query: free-form data that was passed to `alert.oneshot_delete`.
        :return: `alerts` that do not match query (e.g. `query` specifies `{"certificate_id": "xxx"}` and the method
            implementation returns all `alerts` except the ones related to the certificate `xxx`).
        """
        raise NotImplementedError

    async def load(self, alerts):
        """
        This is called on system startup. Returns only those `alerts` that are still applicable to this system (i.e.,
        corresponsing resources still exist).

        :param alerts: all the existing alerts of the class
        :return: `alerts` that should exist on this system.
        """
        return alerts


class SimpleOneShotAlertClass(OneShotAlertClass):
    """
    A simple implementation of `OneShotAlertClass` that pass `args` as `args` when creating an `Alert` and will match
    `args` dict keys (or their subset) when deleting an alert.

    :cvar keys: controls how alerts are deleted:
        `keys = ["id", "name"]` When deleting an alert, only this keys will be compared
        `keys = []`             When deleting an alert, all alerts of this class will be deleted
        `keys = None`           All present alert keys must be equal to the delete query (default)
    """
    keys = None

    async def create(self, args):
        return Alert(self.__class__, args)

    async def delete(self, alerts, query):
        return list(filter(
            lambda alert: (
                any(alert.args[k] != query[k] for k in self.keys) if self.keys is not None
                else alert.args != query
            ),
            alerts
        ))


class DismissableAlertClass:
    async def dismiss(self, alerts, alert):
        raise NotImplementedError


class AlertCategory(enum.Enum):
    APPLICATIONS = "APPLICATIONS"
    AUDIT = "Audit"
    CERTIFICATES = "CERTIFICATES"
    CLUSTERING = "CLUSTERING"
    DIRECTORY_SERVICE = "DIRECTORY_SERVICE"
    HA = "HA"
    HARDWARE = "HARDWARE"
    KMIP = "KMIP"
    PLUGINS = "PLUGINS"
    NETWORK = "NETWORK"
    REPORTING = "REPORTING"
    SECURITY = "SECURITY"
    SHARING = "SHARING"
    STORAGE = "STORAGE"
    SYSTEM = "SYSTEM"
    TASKS = "TASKS"
    TRUENAS_CONNECT = "TRUENAS_CONNECT"
    UPS = "UPS"


alert_category_names = {
    AlertCategory.APPLICATIONS: "Applications",
    AlertCategory.AUDIT: "Audit",
    AlertCategory.CERTIFICATES: "Certificates",
    AlertCategory.CLUSTERING: "Clustering",
    AlertCategory.DIRECTORY_SERVICE: "Directory Service",
    AlertCategory.HA: "High-Availability",
    AlertCategory.HARDWARE: "Hardware",
    AlertCategory.KMIP: "Key Management Interoperability Protocol (KMIP)",
    AlertCategory.PLUGINS: "Plugins",
    AlertCategory.NETWORK: "Network",
    AlertCategory.REPORTING: "Reporting",
    AlertCategory.SECURITY: "Security",
    AlertCategory.SHARING: "Sharing",
    AlertCategory.STORAGE: "Storage",
    AlertCategory.SYSTEM: "System",
    AlertCategory.TASKS: "Tasks",
    AlertCategory.TRUENAS_CONNECT: "TrueNAS Connect Service",
    AlertCategory.UPS: "UPS",
}


assert all([category in alert_category_names for category in AlertCategory]), 'Alert Category Mismatch'


class AlertLevel(enum.Enum):
    INFO = 1
    NOTICE = 2
    WARNING = 3
    ERROR = 4
    CRITICAL = 5
    ALERT = 6
    EMERGENCY = 7


DateTimeType: TypeAlias = datetime


class Alert:
    """
    Alert: a message about a single issues in the system (or a group of similar issues that can be potentially resolved
    with a single action).

    :ivar klass: Alert class: generic description of the alert (e.g. `CertificateIsExpiringAlertClass`)

    :ivar args: specific description of the alert (e.g. `{"name": "my certificate", "days": 3}`).
        The resulting alert text will be obtained by doing `klass.text % args`

    :ivar key: the information that will be used to distinguish this alert from the others of the same class. If empty,
        will default to `args`, which is the most common use case. Can be anything that can be JSON serialized.

        However, for some alerts it makes sense to pass only a subset of args as the key. For example, for a
        `CertificateIsExpiringAlertClass` you may only want to include the certificate name as the key and omit how
        many days are left before the certificate expires. That way, at day change, the alerts "certificate xxx expires
        in 3 days" and "certificate xxx expires in 2 days" will be considered the same alert (as only certificate name
        will be compared) and the newer one will silently replace the old one (in opposite case, an E-Mail would be
        sent claiming that one alert was cleared and another one was added).

    :ivar datetime: timestamp when the alert was first seen.

    :ivar last_occurrence: timestamp when the alert was last seen.

    :ivar node: HA node when the alert was seen.

    :ivar dismissed: whether the alert was dismissed by user.

    :ivar mail: if this parameter is not null, it will be an argument to an extra call to `mail.send` that will be made
        when the alert is first seen.
    """

    klass: type[AlertClass]
    args: dict[str, Any] | list
    key: Any
    datetime: DateTimeType
    last_occurrence: DateTimeType
    node: str | None
    dismissed: bool
    mail: dict | None

    def __init__(
        self,
        klass: type[AlertClass],
        args: Any = None,
        key: Any = undefined,
        datetime: datetime | None = None,
        last_occurrence: datetime | None = None,
        node: str | None = None,
        dismissed: bool | None = None,
        mail: Any = None,
        _uuid: str | None = None,
        _source: Any = None,
        _key: Any = None,
        _text: Any = None,
    ):
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
            return self.text


class AlertSource(CallMixin):
    """
    Alert source: a class that periodically checks for a specific erroneous condition and returns one or multiple
    `Alert` instances.

    :cvar schedule: `BaseSchedule` instance that will be used to determine whether this alert source should be ran at
        any given moment. By default, alert checkers are ran every minute.

    :cvar products: A list of `system.product_type` return values for which this source will be ran.

    :cvar failover_related: should be `true` if this alert is HA failover related. Failover-related alerts are not ran
        within a specific time interval after failover to prevent false positives.

    :cvar run_on_backup_node: set this to `false` to prevent running this alert on HA `BACKUP` node.
    """

    schedule = IntervalSchedule(timedelta())

    products = (ProductType.COMMUNITY_EDITION, ProductType.ENTERPRISE)
    failover_related = False
    run_on_backup_node = True
    require_stable_peer = False

    def __init__(self, middleware):
        self.middleware = middleware

    @property
    def name(self):
        return self.__class__.__name__.replace("AlertSource", "")

    async def check(self) -> list[Alert] | Alert | None:
        """
        This method will be called on the specific `schedule` to check for the alert conditions.

        :return: an `Alert` instance, or a list of `Alert` instances, or `None` for no alerts.
        """
        raise NotImplementedError


class ThreadedAlertSource(AlertSource):
    async def check(self):
        return await self.middleware.run_in_thread(self.check_sync)

    def check_sync(self):
        raise NotImplementedError


class AlertService(CallMixin):
    title = NotImplementedError

    schema = NotImplementedError

    html = False

    def __init__(self, middleware, attributes):
        self.middleware = middleware
        self.attributes = attributes

        self.logger = logging.getLogger(self.__class__.__name__)

    @classmethod
    def name(cls):
        return cls.__name__.replace("AlertService", "")

    async def send(self, alerts, gone_alerts, new_alerts):
        raise NotImplementedError

    async def _format_alerts(self, alerts, gone_alerts, new_alerts):
        hostname = await self.middleware.call("system.hostname")
        if await self.middleware.call("system.is_enterprise"):
            node_map = await self.middleware.call("alert.node_map")
        else:
            node_map = None

        html = format_alerts(ProductName.PRODUCT_NAME, hostname, node_map, alerts, gone_alerts, new_alerts)

        if self.html:
            return html

        return html2text.html2text(html).rstrip()


class ThreadedAlertService(AlertService):
    async def send(self, alerts, gone_alerts, new_alerts):
        return await self.middleware.run_in_thread(self.send_sync, alerts, gone_alerts, new_alerts)

    def send_sync(self, alerts, gone_alerts, new_alerts):
        raise NotImplementedError

    def _format_alerts(self, alerts, gone_alerts, new_alerts):
        hostname = self.middleware.call_sync("system.hostname")
        if self.middleware.call_sync("system.is_enterprise"):
            node_map = self.middleware.call_sync("alert.node_map")
        else:
            node_map = None
        return format_alerts(ProductName.PRODUCT_NAME, hostname, node_map, alerts, gone_alerts, new_alerts)


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


def ellipsis(a, b):
    if len(a) <= b:
        return a

    return a[:(b - 1)] + "…"
