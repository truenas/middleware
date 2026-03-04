from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta
import enum
import json
import logging
from typing import Any, Self, TypeAlias, TYPE_CHECKING

import html2text

from middlewared.alert.schedule import IntervalSchedule
from middlewared.utils import ProductName, ProductType
from middlewared.utils.service.call_mixin import CallMixin

if TYPE_CHECKING:
    from middlewared.main import Middleware

__all__ = [
    "UnavailableException", "AlertClassConfig", "AlertClass", "NonDataclassAlertClass", "OneShotAlertClass",
    "DismissableAlertClass", "AlertCategory", "AlertLevel", "Alert", "AlertSource", "ThreadedAlertSource",
    "AlertService", "ThreadedAlertService", "ProThreadedAlertService", "format_alerts", "ellipsis",
    "alert_category_names",
]

logger = logging.getLogger(__name__)


class UnavailableException(Exception):
    pass


@dataclasses.dataclass(slots=True, frozen=True, kw_only=True)
class AlertClassConfig:
    """
    Configuration for an AlertClass.

    :param category: `AlertCategory` value.

    :param level: Default `AlertLevel` value (alert level can be later changed by user).

    :param title: Short description of the alert class (e.g. "An SSL certificate is expiring").

    :param text: Format string for the alert class instance (e.g. "%(name)s SSL certificate is expiring").

    :param exclude_from_list: Set this to `true` to exclude the alert from the UI configuration. For example, you might
        want to hide some rare legacy hardware-specific alert. It will still be sent if it occurs, but users won't be
        able to disable it or change its level.

    :param products: A list of `system.product_type` return values on which alerts of this class can be emitted.

    :param proactive_support: Set this to `true` if, upon creation of the alert, a support ticket should be open for
        the systems that have a corresponding support license.

    :param proactive_support_notify_gone: Set this to `true` if, upon removal of the alert, a support ticket should be
        open for the systems that have a corresponding support license.

    :param deleted_automatically: (OneShotAlertClass) Set this to `false` if there is no one to call
        `alert.oneshot_delete` when the alert situation is resolved. In that case, the alert will be deleted when the
        user dismisses it.

    :param expires_after: (OneShotAlertClass) Lifetime for the alert.

    :param keys: (OneShotAlertClass) Controls how alerts are deleted:
        `keys = ["id", "name"]` When deleting an alert, only these keys will be compared
        `keys = []`             When deleting an alert, all alerts of this class will be deleted
        `keys = None`           Use `key()` method for matching (default)

    :param name: class name (without Alert suffix). Will be set by `AlertClassMeta` on each class creation.
    """

    category: AlertCategory
    level: AlertLevel
    title: str
    text: str | None = None
    exclude_from_list: bool = False
    products: tuple[str, ...] = (ProductType.COMMUNITY_EDITION, ProductType.ENTERPRISE)
    proactive_support: bool = False
    proactive_support_notify_gone: bool = False
    deleted_automatically: bool = True
    expires_after: timedelta | None = None
    keys: list[str] | None = None
    name: str = "NOTSET"


class AlertClass:
    """
    Alert class: a description of a specific type of issue that can exist in the system.

    Subclasses must define a `config` class variable of type `AlertClassConfig`.

    Subclasses may be:
    - A `@dataclass` with named fields (for alerts with dict args)
    - A `NonDataclassAlertClass[T]` subclass (for alerts with string or list args)
    - A plain class with no fields (for alerts with no args)
    """

    classes: list[type[AlertClass]] = []
    class_by_name: dict[str, type[AlertClass]] = {}

    config: AlertClassConfig

    def __init_subclass__(cls):
        super().__init_subclass__()

        if cls.__name__ not in ["OneShotAlertClass"]:
            if not cls.__name__.endswith("Alert"):
                raise NameError(f"Invalid alert class name {cls.__name__}")

            name = cls.__name__.removesuffix("Alert")
            cls.config = dataclasses.replace(cls.config, name=name)

            AlertClass.classes.append(cls)
            AlertClass.class_by_name[name] = cls

    def args(self) -> Any:
        if dataclasses.is_dataclass(self):
            return dataclasses.asdict(self)

        return None

    @classmethod
    def from_args(cls, args: Any) -> Self:
        if dataclasses.is_dataclass(cls):
            return cls(**args)

        return cls()

    @classmethod
    def key(cls, args: Any) -> Any:
        """Return the deduplication key for an alert with the given args.

        Override this to customize which fields are used for deduplication.
        Default: the full args value.
        """
        return args

    @classmethod
    def format(cls, args: Any) -> str:
        if cls.config.text is None:
            return cls.config.title

        if args is None:
            return cls.config.text

        return cls.config.text % (tuple(args) if isinstance(args, list) else args)


class NonDataclassAlertClass[T]:
    """Mixin for alert classes that use positional format strings (string or list args).

    Must be listed FIRST in bases (before AlertClass) for correct MRO:
        class MyAlert(NonDataclassAlertClass[str], AlertClass): ...
    """

    def __init__(self, args: T):
        self._args = args

    def args(self) -> T:
        return self._args

    @classmethod
    def from_args(cls, args: Any) -> Self:
        return cls(args)


class OneShotAlertClass(AlertClass):
    """
    One-shot alert mixin: add this to `AlertClass` superclass list for alerts that are created not by an
    `AlertSource` but using `alert.oneshot_create` API method.

    Configure `deleted_automatically`, `expires_after`, and `keys` via `AlertClassConfig`.

    Override `AlertClass.key()` to set a custom deduplication key derived from `args`.
    """

    @classmethod
    async def delete(cls, alerts: list[Alert[Self]], query: dict[str, Any] | None) -> list[Alert[Self]]:
        """
        Returns only those `alerts` that do not match `query` that was passed to `alert.oneshot_delete`.

        :param alerts: all the alerts of this class.
        :param query: free-form data that was passed to `alert.oneshot_delete`.
        :return: `alerts` that do not match query (e.g. `query` specifies `{"certificate_id": "xxx"}` and the method
            implementation returns all `alerts` except the ones related to the certificate `xxx`).
        """
        if cls.config.keys is not None:
            if query is None:
                raise ValueError("`query` cannot be `None`")

            return [alert for alert in alerts if any(getattr(alert.instance, k) != query[k] for k in cls.config.keys)]

        return [alert for alert in alerts if cls.key(alert.instance.args()) != query]

    @classmethod
    async def load(cls, middleware: Middleware, alerts: list[Alert[Self]]) -> list[Alert[Self]]:
        """
        This is called on system startup. Returns only those `alerts` that are still applicable to this system (i.e.,
        corresponding resources still exist).

        :param middleware: the middleware instance.
        :param alerts: all the existing alerts of the class.
        :return: `alerts` that should exist on this system.
        """
        return alerts


class DismissableAlertClass(AlertClass):
    @classmethod
    async def dismiss(cls, middleware: Middleware, alerts: list[Alert[Self]], alert: Alert[Self]) -> list[Alert[Self]]:
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


class Alert[T: AlertClass]:
    """
    Alert: a message about a single issues in the system (or a group of similar issues that can be potentially resolved
    with a single action).

    :ivar klass: Alert class: generic description of the alert (e.g. `CertificateIsExpiringAlert`)

    :ivar args: specific description of the alert (e.g. `{"name": "my certificate", "days": 3}`).
        The resulting alert text will be obtained by doing `klass.text % args`

    :ivar key: the information that will be used to distinguish this alert from the others of the same class. If empty,
        will default to `args`, which is the most common use case. Can be anything that can be JSON serialized.

        However, for some alerts it makes sense to pass only a subset of args as the key. For example, for a
        `CertificateIsExpiringAlert` you may only want to include the certificate name as the key and omit how
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

    def __init__(
        self,
        instance: T,
        datetime: datetime | None = None,
        last_occurrence: datetime | None = None,
        node: str | None = None,
        dismissed: bool | None = None,
        mail: Any = None,
        _uuid: str | None = None,
        _source: str | None = None,
        _key: str | None = None,
        _text: str | None = None,
    ):
        self.instance = instance
        self.datetime = datetime
        self.last_occurrence = last_occurrence or datetime
        self.node = node
        self.dismissed = dismissed
        self.mail = mail

        self.uuid = _uuid
        self.source = _source

        if _key is None:
            self.key = json.dumps(self.instance.key(self.instance.args()), sort_keys=True)
        else:
            self.key = _key

        self.text = _text or self.instance.config.text or self.instance.config.title

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Alert):
            return NotImplemented

        return self.__dict__ == other.__dict__

    def __repr__(self) -> str:
        return repr(self.__dict__)

    @property
    def formatted(self) -> str:
        try:
            return self.instance.format(self.instance.args())
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

    def __init__(self, middleware: Middleware):
        self.middleware = middleware

    @property
    def name(self) -> str:
        return self.__class__.__name__.replace("AlertSource", "")

    async def check(self) -> list[Alert[Any]] | Alert[Any] | None:
        """
        This method will be called on the specific `schedule` to check for the alert conditions.

        :return: an `Alert` instance, or a list of `Alert` instances, or `None` for no alerts.
        """
        raise NotImplementedError


class ThreadedAlertSource(AlertSource):
    async def check(self) -> list[Alert[Any]] | Alert[Any] | None:
        return await self.middleware.run_in_thread(self.check_sync)

    def check_sync(self) -> list[Alert[Any]] | Alert[Any] | None:
        raise NotImplementedError


class AlertService(CallMixin):
    title: str
    html: bool = False

    def __init__(self, middleware: Middleware, attributes: dict[str, Any]):
        self.middleware = middleware
        self.attributes = attributes

        self.logger = logging.getLogger(self.__class__.__name__)

    @classmethod
    def name(cls) -> str:
        return cls.__name__.replace("AlertService", "")

    async def send(
        self,
        alerts: list[Alert[Any]],
        gone_alerts: list[Alert[Any]],
        new_alerts: list[Alert[Any]],
    ) -> None:
        raise NotImplementedError

    async def _format_alerts(
        self,
        alerts: list[Alert[Any]],
        gone_alerts: list[Alert[Any]],
        new_alerts: list[Alert[Any]],
    ) -> str:
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
    async def send(
        self,
        alerts: list[Alert[Any]],
        gone_alerts: list[Alert[Any]],
        new_alerts: list[Alert[Any]],
    ) -> None:
        return await self.middleware.run_in_thread(self.send_sync, alerts, gone_alerts, new_alerts)

    def send_sync(
        self,
        alerts: list[Alert[Any]],
        gone_alerts: list[Alert[Any]],
        new_alerts: list[Alert[Any]],
    ) -> None:
        raise NotImplementedError

    def _format_alerts_sync(
        self,
        alerts: list[Alert[Any]],
        gone_alerts: list[Alert[Any]],
        new_alerts: list[Alert[Any]],
    ) -> str:
        hostname = self.middleware.call_sync("system.hostname")
        if self.middleware.call_sync("system.is_enterprise"):
            node_map = self.middleware.call_sync("alert.node_map")
        else:
            node_map = None

        html = format_alerts(ProductName.PRODUCT_NAME, hostname, node_map, alerts, gone_alerts, new_alerts)

        if self.html:
            return html

        return html2text.html2text(html).rstrip()


class ProThreadedAlertService(ThreadedAlertService):
    def send_sync(
        self,
        alerts: list[Alert[Any]],
        gone_alerts: list[Alert[Any]],
        new_alerts: list[Alert[Any]],
    ) -> None:
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

    def create_alert(self, alert: Alert[Any]) -> None:
        raise NotImplementedError

    def delete_alert(self, alert: Alert[Any]) -> None:
        raise NotImplementedError


def format_alerts(
    product_name: str,
    hostname: str,
    node_map: dict[str, str],
    alerts: list[Alert[Any]],
    gone_alerts: list[Alert[Any]],
    new_alerts: list[Alert[Any]],
) -> str:
    text = f"{product_name} @ {hostname}<br><br>"

    if len(alerts) == 1 and len(gone_alerts) == 0 and len(new_alerts) == 1 and new_alerts[0].instance.config.name == "Test":
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


def format_alert(alert: Alert[Any], node_map: dict[str, str]) -> str:
    return (f"{node_map[alert.node]} - " if alert.node is not None and node_map else "") + alert.formatted


def ellipsis(s: str, length: int) -> str:
    if len(s) <= length:
        return s

    return s[:(length - 1)] + "…"
