from collections import defaultdict, namedtuple
import copy
from datetime import datetime, timezone
import errno
import os
import textwrap
import time
import traceback
import uuid

from middlewared.alert.base import (
    AlertCategory,
    alert_category_names,
    AlertClass,
    OneShotAlertClass,
    SimpleOneShotAlertClass,
    DismissableAlertClass,
    AlertLevel,
    Alert,
    AlertSource,
    FilePresenceAlertSource,
    ThreadedAlertSource,
    ThreadedAlertService,
    ProThreadedAlertService,
)
from middlewared.alert.base import UnavailableException, AlertService as _AlertService
from middlewared.client.client import ReserveFDException
from middlewared.schema import accepts, Any, Bool, Datetime, Dict, Int, List, Patch, returns, Ref, Str
from middlewared.service import (
    ConfigService, CRUDService, Service, ValidationErrors,
    job, periodic, private,
)
from middlewared.service_exception import CallError
import middlewared.sqlalchemy as sa
from middlewared.validators import validate_attributes
from middlewared.utils import bisect
from middlewared.utils.plugins import load_modules, load_classes
from middlewared.utils.python import get_middlewared_dir

POLICIES = ["IMMEDIATELY", "HOURLY", "DAILY", "NEVER"]
DEFAULT_POLICY = "IMMEDIATELY"

ALERT_SOURCES = {}
ALERT_SERVICES_FACTORIES = {}

AlertSourceLock = namedtuple("AlertSourceLock", ["source_name", "expires_at"])

SEND_ALERTS_ON_READY = False


class AlertModel(sa.Model):
    __tablename__ = 'system_alert'

    id = sa.Column(sa.Integer(), primary_key=True)
    node = sa.Column(sa.String(100))
    source = sa.Column(sa.Text())
    key = sa.Column(sa.Text())
    datetime = sa.Column(sa.DateTime())
    last_occurrence = sa.Column(sa.DateTime())
    text = sa.Column(sa.Text())
    args = sa.Column(sa.JSON(type=None))
    dismissed = sa.Column(sa.Boolean())
    uuid = sa.Column(sa.Text())
    klass = sa.Column(sa.Text())


class AlertSourceRunFailedAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.CRITICAL
    title = "Alert Check Failed"
    text = "Failed to check for alert %(source_name)s:\n%(traceback)s"

    exclude_from_list = True


class AlertSourceRunFailedOnBackupNodeAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.CRITICAL
    title = "Alert Check Failed (Standby Controller)"
    text = "Failed to check for alert %(source_name)s on standby controller:\n%(traceback)s"

    exclude_from_list = True


class AutomaticAlertFailedAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = "Failed to Notify iXsystems About Alert"
    text = textwrap.dedent("""\
        Creating an automatic alert for iXsystems about system %(serial)s failed: %(error)s.
        Please contact iXsystems Support: https://www.ixsystems.com/support/

        Alert:

        %(alert)s
    """)

    exclude_from_list = True

    deleted_automatically = False


class TestAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.CRITICAL
    title = "Test alert"

    exclude_from_list = True


class AlertPolicy:
    def __init__(self, key=lambda now: now):
        self.key = key

        self.last_key_value = None
        self.last_key_value_alerts = {}

    def receive_alerts(self, now, alerts):
        alerts = {alert.uuid: alert for alert in alerts}
        gone_alerts = []
        new_alerts = []
        key = self.key(now)
        if key != self.last_key_value:
            gone_alerts = [alert for alert in self.last_key_value_alerts.values() if alert.uuid not in alerts]
            new_alerts = [alert for alert in alerts.values() if alert.uuid not in self.last_key_value_alerts]

            self.last_key_value = key
            self.last_key_value_alerts = alerts

        return gone_alerts, new_alerts


def get_alert_level(alert, classes):
    return AlertLevel[classes.get(alert.klass.name, {}).get("level", alert.klass.level.name)]


def get_alert_policy(alert, classes):
    return classes.get(alert.klass.name, {}).get("policy", DEFAULT_POLICY)


class AlertSerializer:
    def __init__(self, middleware):
        self.middleware = middleware

        self.initialized = False
        self.product_type = None
        self.classes = None
        self.nodes = None

    async def serialize(self, alert):
        await self._ensure_initialized()

        return dict(
            alert.__dict__,
            id=alert.uuid,
            node=self.nodes[alert.node],
            klass=alert.klass.name,
            level=self.classes.get(alert.klass.name, {}).get("level", alert.klass.level.name),
            formatted=alert.formatted,
            one_shot=issubclass(alert.klass, OneShotAlertClass) and not alert.klass.deleted_automatically
        )

    async def should_show_alert(self, alert):
        await self._ensure_initialized()

        if self.product_type not in alert.klass.products:
            return False

        if self.classes.get(alert.klass.name, {}).get("policy") == "NEVER":
            return False

        return True

    async def _ensure_initialized(self):
        if not self.initialized:
            self.product_type = await self.middleware.call("alert.product_type")
            self.classes = (await self.middleware.call("alertclasses.config"))["classes"]
            self.nodes = await self.middleware.call("alert.node_map")

            self.initialized = True


class AlertService(Service):
    class Config:
        cli_namespace = "system.alert"

    def __init__(self, middleware):
        super().__init__(middleware)

        self.blocked_sources = defaultdict(set)
        self.sources_locks = {}

        self.blocked_failover_alerts_until = 0

    @private
    async def load(self):
        main_sources_dir = os.path.join(get_middlewared_dir(), "alert", "source")
        sources_dirs = [os.path.join(overlay_dir, "alert", "source") for overlay_dir in self.middleware.overlay_dirs]
        sources_dirs.insert(0, main_sources_dir)
        for sources_dir in sources_dirs:
            for module in load_modules(sources_dir):
                for cls in load_classes(module, AlertSource, (FilePresenceAlertSource, ThreadedAlertSource)):
                    source = cls(self.middleware)
                    if source.name in ALERT_SOURCES:
                        raise RuntimeError(f"Alert source {source.name} is already registered")
                    ALERT_SOURCES[source.name] = source

        main_services_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), os.path.pardir, "alert",
                                         "service")
        services_dirs = [os.path.join(overlay_dir, "alert", "service") for overlay_dir in self.middleware.overlay_dirs]
        services_dirs.insert(0, main_services_dir)
        for services_dir in services_dirs:
            for module in load_modules(services_dir):
                for cls in load_classes(module, _AlertService, (ThreadedAlertService, ProThreadedAlertService)):
                    ALERT_SERVICES_FACTORIES[cls.name()] = cls

    @private
    async def initialize(self, load=True):
        is_enterprise = await self.middleware.call("system.is_enterprise")

        self.node = "A"
        if is_enterprise:
            if await self.middleware.call("failover.node") == "B":
                self.node = "B"

        self.alerts = []
        if load:
            for alert in await self.middleware.call("datastore.query", "system.alert"):
                del alert["id"]

                try:
                    alert["klass"] = AlertClass.class_by_name[alert["klass"]]
                except KeyError:
                    self.logger.info("Alert class %r is no longer present", alert["klass"])
                    continue

                alert["_uuid"] = alert.pop("uuid")
                alert["_source"] = alert.pop("source")
                alert["_key"] = alert.pop("key")
                alert["_text"] = alert.pop("text")

                alert = Alert(**alert)

                if not any(a.uuid == alert.uuid for a in self.alerts):
                    self.alerts.append(alert)

        self.alert_source_last_run = defaultdict(lambda: datetime.min)

        self.policies = {
            "IMMEDIATELY": AlertPolicy(),
            "HOURLY": AlertPolicy(lambda d: (d.date(), d.hour)),
            "DAILY": AlertPolicy(lambda d: (d.date())),
            "NEVER": AlertPolicy(lambda d: None),
        }
        for policy in self.policies.values():
            policy.receive_alerts(datetime.utcnow(), self.alerts)

    @private
    async def terminate(self):
        await self.flush_alerts()

    @accepts()
    @returns(List('alert_policies', items=[Str('policy', enum=POLICIES)]))
    async def list_policies(self):
        """
        List all alert policies which indicate the frequency of the alerts.
        """
        return POLICIES

    @accepts()
    @returns(List('categories', items=[Dict(
        'category',
        Str('id'),
        Str('title'),
        List('classes', items=[Dict(
            'category_class',
            Str('id'),
            Str('title'),
            Str('level'),
        )])
    )]))
    async def list_categories(self):
        """
        List all types of alerts which the system can issue.
        """

        product_type = await self.middleware.call("alert.product_type")

        classes = [alert_class for alert_class in AlertClass.classes
                   if product_type in alert_class.products and not alert_class.exclude_from_list]

        return [
            {
                "id": alert_category.name,
                "title": alert_category_names[alert_category],
                "classes": sorted(
                    [
                        {
                            "id": alert_class.name,
                            "title": alert_class.title,
                            "level": alert_class.level.name,
                        }
                        for alert_class in classes
                        if alert_class.category == alert_category
                    ],
                    key=lambda klass: klass["title"]
                )
            }
            for alert_category in AlertCategory
            if any(alert_class.category == alert_category for alert_class in classes)
        ]

    @private
    async def list_sources(self):
        # TODO: this is a deprecated method for backward compatibility

        return [
            {
                "name": klass["id"],
                "title": klass["title"],
            }
            for klass in sum([v["classes"] for v in await self.list_categories()], [])
        ]

    @accepts()
    @returns(List('alerts', items=[Dict(
        'alert',
        Str('uuid'),
        Str('source'),
        Str('klass'),
        Any('args'),
        Str('node'),
        Str('key'),
        Datetime('datetime'),
        Datetime('last_occurrence'),
        Bool('dismissed'),
        Any('mail', null=True),
        Str('text'),
        Str('id'),
        Str('level'),
        Str('formatted', null=True),
        Bool('one_shot'),
    )]))
    async def list(self):
        """
        List all types of alerts including active/dismissed currently in the system.
        """

        as_ = AlertSerializer(self.middleware)

        return [
            await as_.serialize(alert)
            for alert in sorted(self.alerts, key=lambda alert: (alert.klass.title, alert.datetime))
            if await as_.should_show_alert(alert)
        ]

    @private
    async def node_map(self):
        nodes = {
            'A': 'Controller A',
            'B': 'Controller B',
        }
        if await self.middleware.call('failover.licensed'):
            node = await self.middleware.call('failover.node')
            status = await self.middleware.call('failover.status')
            if status == 'MASTER':
                if node == 'A':
                    nodes = {
                        'A': 'Active Controller (A)',
                        'B': 'Standby Controller (B)',
                    }
                else:
                    nodes = {
                        'A': 'Standby Controller (A)',
                        'B': 'Active Controller (B)',
                    }
            else:
                nodes[node] = f'{status.title()} Controller ({node})'

        return nodes

    def __alert_by_uuid(self, uuid):
        try:
            return [a for a in self.alerts if a.uuid == uuid][0]
        except IndexError:
            return None

    @accepts(Str("uuid"))
    @returns()
    async def dismiss(self, uuid):
        """
        Dismiss `id` alert.
        """

        alert = self.__alert_by_uuid(uuid)
        if alert is None:
            return

        if issubclass(alert.klass, DismissableAlertClass):
            related_alerts, unrelated_alerts = bisect(lambda a: (a.node, a.klass) == (alert.node, alert.klass),
                                                      self.alerts)
            left_alerts = await alert.klass(self.middleware).dismiss(related_alerts, alert)
            for deleted_alert in related_alerts:
                if deleted_alert not in left_alerts:
                    self._delete_on_dismiss(deleted_alert)
        elif issubclass(alert.klass, OneShotAlertClass) and not alert.klass.deleted_automatically:
            self._delete_on_dismiss(alert)
        else:
            alert.dismissed = True
            await self._send_alert_changed_event(alert)

    def _delete_on_dismiss(self, alert):
        self.alerts.remove(alert)

        for policy in self.policies.values():
            policy.last_key_value_alerts.pop(alert.uuid, None)

        self._send_alert_deleted_event(alert)

    @accepts(Str("uuid"))
    @returns()
    async def restore(self, uuid):
        """
        Restore `id` alert which had been dismissed.
        """

        alert = self.__alert_by_uuid(uuid)
        if alert is None:
            return

        alert.dismissed = False

        await self._send_alert_changed_event(alert)

    async def _send_alert_changed_event(self, alert):
        as_ = AlertSerializer(self.middleware)
        if await as_.should_show_alert(alert):
            self.middleware.send_event("alert.list", "CHANGED", id=alert.uuid, fields=await as_.serialize(alert))

    def _send_alert_deleted_event(self, alert):
        self.middleware.send_event("alert.list", "CHANGED", id=alert.uuid, cleared=True)

    @periodic(60)
    @private
    @job(lock="process_alerts", transient=True, lock_queue_size=1)
    async def process_alerts(self, job):
        if not await self.__should_run_or_send_alerts():
            return

        valid_alerts = copy.deepcopy(self.alerts)
        await self.__run_alerts()

        self.__expire_alerts()

        if not await self.__should_run_or_send_alerts():
            self.alerts = valid_alerts
            return

        await self.middleware.call("alert.send_alerts")

    @private
    @job(lock="process_alerts", transient=True)
    async def send_alerts(self, job):
        global SEND_ALERTS_ON_READY

        if await self.middleware.call("system.state") != "READY":
            SEND_ALERTS_ON_READY = True
            return

        product_type = await self.middleware.call("alert.product_type")
        classes = (await self.middleware.call("alertclasses.config"))["classes"]

        now = datetime.utcnow()
        for policy_name, policy in self.policies.items():
            gone_alerts, new_alerts = policy.receive_alerts(now, self.alerts)

            for alert_service_desc in await self.middleware.call("datastore.query", "system.alertservice",
                                                                 [["enabled", "=", True]]):
                service_level = AlertLevel[alert_service_desc["level"]]

                service_alerts = [
                    alert for alert in self.alerts
                    if (
                        product_type in alert.klass.products and
                        get_alert_level(alert, classes).value >= service_level.value and
                        get_alert_policy(alert, classes) != "NEVER"
                    )
                ]
                service_gone_alerts = [
                    alert for alert in gone_alerts
                    if (
                        product_type in alert.klass.products and
                        get_alert_level(alert, classes).value >= service_level.value and
                        get_alert_policy(alert, classes) == policy_name
                    )
                ]
                service_new_alerts = [
                    alert for alert in new_alerts
                    if (
                        product_type in alert.klass.products and
                        get_alert_level(alert, classes).value >= service_level.value and
                        get_alert_policy(alert, classes) == policy_name
                    )
                ]
                for gone_alert in list(service_gone_alerts):
                    for new_alert in service_new_alerts:
                        if gone_alert.klass == new_alert.klass and gone_alert.key == new_alert.key:
                            service_gone_alerts.remove(gone_alert)
                            service_new_alerts.remove(new_alert)
                            break

                if not service_gone_alerts and not service_new_alerts:
                    continue

                factory = ALERT_SERVICES_FACTORIES.get(alert_service_desc["type"])
                if factory is None:
                    self.logger.error("Alert service %r does not exist", alert_service_desc["type"])
                    continue

                try:
                    alert_service = factory(self.middleware, alert_service_desc["attributes"])
                except Exception:
                    self.logger.error("Error creating alert service %r with parameters=%r",
                                      alert_service_desc["type"], alert_service_desc["attributes"], exc_info=True)
                    continue

                alerts = [alert for alert in service_alerts if not alert.dismissed]
                service_gone_alerts = [alert for alert in service_gone_alerts if not alert.dismissed]
                service_new_alerts = [alert for alert in service_new_alerts if not alert.dismissed]

                if alerts or service_gone_alerts or service_new_alerts:
                    try:
                        await alert_service.send(alerts, service_gone_alerts, service_new_alerts)
                    except Exception:
                        self.logger.error("Error in alert service %r", alert_service_desc["type"], exc_info=True)

            if policy_name == "IMMEDIATELY":
                as_ = AlertSerializer(self.middleware)
                for alert in gone_alerts:
                    if await as_.should_show_alert(alert):
                        self._send_alert_deleted_event(alert)
                for alert in new_alerts:
                    if await as_.should_show_alert(alert):
                        self.middleware.send_event(
                            "alert.list", "ADDED", id=alert.uuid, fields=await as_.serialize(alert),
                        )

                for alert in new_alerts:
                    if alert.mail:
                        await self.middleware.call("mail.send", alert.mail)

                if await self.middleware.call("system.is_enterprise"):
                    new_hardware_alerts = [alert for alert in new_alerts if alert.klass.hardware]
                    if new_hardware_alerts:
                        if await self.middleware.call("support.is_available_and_enabled"):
                            support = await self.middleware.call("support.config")
                            msg = [f"* {alert.formatted}" for alert in new_hardware_alerts]

                            serial = (await self.middleware.call("system.dmidecode_info"))["system-serial-number"]

                            for name, verbose_name in await self.middleware.call("support.fields"):
                                value = support[name]
                                if value:
                                    msg += ["", "{}: {}".format(verbose_name, value)]

                            msg = "\n".join(msg)

                            job = await self.middleware.call("support.new_ticket", {
                                "title": "Automatic alert (%s)" % serial,
                                "body": msg,
                                "attach_debug": False,
                                "category": "Hardware",
                                "criticality": "Loss of Functionality",
                                "environment": "Production",
                                "name": "Automatic Alert",
                                "email": "auto-support@ixsystems.com",
                                "phone": "-",
                            })
                            await job.wait()
                            if job.error:
                                await self.middleware.call("alert.oneshot_create", "AutomaticAlertFailed",
                                                           {"serial": serial, "alert": msg, "error": str(job.error)})

    def __uuid(self):
        return str(uuid.uuid4())

    async def __should_run_or_send_alerts(self):
        if await self.middleware.call('system.state') != 'READY':
            return False

        if await self.middleware.call('failover.licensed'):
            status = await self.middleware.call('failover.status')
            if status == 'BACKUP' or await self.middleware.call('failover.in_progress'):
                return False

        return True

    async def __run_alerts(self):
        master_node = "A"
        backup_node = "B"
        product_type = await self.middleware.call("alert.product_type")
        run_on_backup_node = False
        run_failover_related = False
        if product_type == "ENTERPRISE":
            if await self.middleware.call("failover.licensed"):
                if await self.middleware.call("failover.node") == "B":
                    master_node = "B"
                    backup_node = "A"
                try:
                    remote_version = await self.middleware.call("failover.call_remote", "system.version")
                    remote_system_state = await self.middleware.call("failover.call_remote", "system.state")
                    remote_failover_status = await self.middleware.call("failover.call_remote",
                                                                        "failover.status")
                except Exception:
                    pass
                else:
                    if remote_version == await self.middleware.call("system.version"):
                        if remote_system_state == "READY" and remote_failover_status == "BACKUP":
                            run_on_backup_node = True

            run_failover_related = time.monotonic() > self.blocked_failover_alerts_until

        for k, source_lock in list(self.sources_locks.items()):
            if source_lock.expires_at <= time.monotonic():
                await self.unblock_source(k)

        for alert_source in ALERT_SOURCES.values():
            if product_type not in alert_source.products:
                continue

            if alert_source.failover_related and not run_failover_related:
                continue

            if not alert_source.schedule.should_run(datetime.utcnow(), self.alert_source_last_run[alert_source.name]):
                continue

            self.alert_source_last_run[alert_source.name] = datetime.utcnow()

            alerts_a = [alert
                        for alert in self.alerts
                        if alert.node == master_node and alert.source == alert_source.name]
            locked = False
            if self.blocked_sources[alert_source.name]:
                self.logger.debug("Not running alert source %r because it is blocked", alert_source.name)
                locked = True
            else:
                self.logger.trace("Running alert source: %r", alert_source.name)

                try:
                    alerts_a = await self.__run_source(alert_source.name)
                except UnavailableException:
                    pass
            for alert in alerts_a:
                alert.node = master_node

            alerts_b = []
            if run_on_backup_node and alert_source.run_on_backup_node:
                try:
                    alerts_b = [alert
                                for alert in self.alerts
                                if alert.node == backup_node and alert.source == alert_source.name]
                    try:
                        if not locked:
                            alerts_b = await self.middleware.call("failover.call_remote", "alert.run_source",
                                                                  [alert_source.name])

                            alerts_b = [Alert(**dict({k: v for k, v in alert.items()
                                                      if k in ["args", "datetime", "last_occurrence", "dismissed",
                                                               "mail"]},
                                                     klass=AlertClass.class_by_name[alert["klass"]],
                                                     _source=alert["source"],
                                                     _key=alert["key"]))
                                        for alert in alerts_b]
                    except CallError as e:
                        if e.errno in [errno.ECONNABORTED, errno.ECONNREFUSED, errno.ECONNRESET, errno.EHOSTDOWN,
                                       errno.ETIMEDOUT, CallError.EALERTCHECKERUNAVAILABLE]:
                            pass
                        else:
                            raise
                except ReserveFDException:
                    self.logger.debug('Failed to reserve a privileged port')
                except Exception:
                    alerts_b = [
                        Alert(AlertSourceRunFailedOnBackupNodeAlertClass,
                              args={
                                  "source_name": alert_source.name,
                                  "traceback": traceback.format_exc(),
                              },
                              _source=alert_source.name)
                    ]

            for alert in alerts_b:
                alert.node = backup_node

            for alert in alerts_a + alerts_b:
                self.__handle_alert(alert)

            self.alerts = (
                [a for a in self.alerts if a.source != alert_source.name] +
                alerts_a +
                alerts_b
            )

    def __handle_alert(self, alert):
        try:
            existing_alert = [
                a for a in self.alerts
                if (a.node, a.source, a.klass, a.key) == (alert.node, alert.source, alert.klass, alert.key)
            ][0]
        except IndexError:
            existing_alert = None

        if existing_alert is None:
            alert.uuid = self.__uuid()
        else:
            alert.uuid = existing_alert.uuid
        if existing_alert is None:
            alert.datetime = alert.datetime or datetime.utcnow()
            if alert.datetime.tzinfo is not None:
                alert.datetime = alert.datetime.astimezone(timezone.utc).replace(tzinfo=None)
        else:
            alert.datetime = existing_alert.datetime
        alert.last_occurrence = datetime.utcnow()
        if existing_alert is None:
            alert.dismissed = False
        else:
            alert.dismissed = existing_alert.dismissed

    def __expire_alerts(self):
        self.alerts = list(filter(lambda alert: not self.__should_expire_alert(alert), self.alerts))

    def __should_expire_alert(self, alert):
        if issubclass(alert.klass, OneShotAlertClass):
            if alert.klass.expires_after is not None:
                return alert.last_occurrence < datetime.utcnow() - alert.klass.expires_after

        return False

    @private
    async def run_source(self, source_name):
        try:
            return [dict(alert.__dict__, klass=alert.klass.name)
                    for alert in await self.__run_source(source_name)]
        except UnavailableException:
            raise CallError("This alert checker is unavailable", CallError.EALERTCHECKERUNAVAILABLE)

    @private
    async def block_source(self, source_name, timeout=3600):
        if source_name not in ALERT_SOURCES:
            raise CallError("Invalid alert source")

        lock = str(uuid.uuid4())
        self.blocked_sources[source_name].add(lock)
        self.sources_locks[lock] = AlertSourceLock(source_name, time.monotonic() + timeout)
        return lock

    @private
    async def unblock_source(self, lock):
        source_lock = self.sources_locks.pop(lock, None)
        if source_lock:
            self.blocked_sources[source_lock.source_name].remove(lock)

    @private
    async def block_failover_alerts(self):
        # This values come from observation from support of how long a M-series boot can take.
        self.blocked_failover_alerts_until = time.monotonic() + 900

    async def __run_source(self, source_name):
        alert_source = ALERT_SOURCES[source_name]

        try:
            alerts = (await alert_source.check()) or []
        except UnavailableException:
            raise
        except Exception as e:
            if isinstance(e, CallError) and e.errno in [errno.ECONNABORTED, errno.ECONNREFUSED, errno.ECONNRESET,
                                                        errno.EHOSTDOWN, errno.ETIMEDOUT]:
                alerts = [
                    Alert(AlertSourceRunFailedAlertClass,
                          args={
                              "source_name": alert_source.name,
                              "traceback": str(e),
                          })
                ]
            else:
                alerts = [
                    Alert(AlertSourceRunFailedAlertClass,
                          args={
                              "source_name": alert_source.name,
                              "traceback": traceback.format_exc(),
                          })
                ]
        else:
            if not isinstance(alerts, list):
                alerts = [alerts]

        for alert in alerts:
            alert.source = source_name

        return alerts

    @periodic(3600, run_on_start=False)
    @private
    async def flush_alerts(self):
        if await self.middleware.call('failover.licensed'):
            if await self.middleware.call('failover.status') == 'BACKUP':
                return

        await self.middleware.call("datastore.delete", "system.alert", [])

        for alert in self.alerts:
            d = alert.__dict__.copy()
            d["klass"] = d["klass"].name
            del d["mail"]
            await self.middleware.call("datastore.insert", "system.alert", d)

    @private
    @accepts(Str("klass"), Any("args", null=True))
    @job(lock="process_alerts", transient=True)
    async def oneshot_create(self, job, klass, args):
        try:
            klass = AlertClass.class_by_name[klass]
        except KeyError:
            raise CallError(f"Invalid alert class: {klass!r}")

        if not issubclass(klass, OneShotAlertClass):
            raise CallError(f"Alert class {klass!r} is not a one-shot alert class")

        alert = await klass(self.middleware).create(args)
        if alert is None:
            return

        alert.source = ""
        alert.klass = alert.klass

        alert.node = self.node

        self.__handle_alert(alert)

        self.alerts = [a for a in self.alerts if a.uuid != alert.uuid] + [alert]

        await self.middleware.call("alert.send_alerts")

    @private
    @accepts(Str("klass"), Any("query", null=True))
    @job(lock="process_alerts", transient=True)
    async def oneshot_delete(self, job, klass, query):
        try:
            klass = AlertClass.class_by_name[klass]
        except KeyError:
            raise CallError(f"Invalid alert source: {klass!r}")

        if not issubclass(klass, OneShotAlertClass):
            raise CallError(f"Alert class {klass!r} is not a one-shot alert source")

        related_alerts, unrelated_alerts = bisect(lambda a: (a.node, a.klass) == (self.node, klass),
                                                  self.alerts)
        left_alerts = await klass(self.middleware).delete(related_alerts, query)
        deleted = False
        for deleted_alert in related_alerts:
            if deleted_alert not in left_alerts:
                self.alerts.remove(deleted_alert)
                deleted = True

        if deleted:
            await self.middleware.call("alert.send_alerts")

    @private
    def alert_source_clear_run(self, name):
        alert_source = ALERT_SOURCES.get(name)
        if not alert_source:
            raise CallError("Alert source {name!r} not found.", errno.ENOENT)

        self.alert_source_last_run[alert_source.name] = datetime.min

    @private
    async def product_type(self):
        return await self.middleware.call("system.product_type")


class AlertServiceModel(sa.Model):
    __tablename__ = 'system_alertservice'

    id = sa.Column(sa.Integer(), primary_key=True)
    name = sa.Column(sa.String(120))
    type = sa.Column(sa.String(20))
    attributes = sa.Column(sa.JSON())
    enabled = sa.Column(sa.Boolean())
    level = sa.Column(sa.String(20))


class AlertServiceService(CRUDService):
    class Config:
        datastore = "system.alertservice"
        datastore_extend = "alertservice._extend"
        datastore_order_by = ["name"]
        cli_namespace = "system.alert.service"

    ENTRY = Patch(
        'alert_service_create', 'alertservice_entry',
        ('add', Int('id')),
        ('add', Str('type__title')),
    )

    @accepts()
    @returns(List('alert_service_types', items=[Dict(
        'alert_service_type',
        Str('name', required=True),
        Str('title', required=True),
    )]))
    async def list_types(self):
        """
        List all types of supported Alert services which can be configured with the system.
        """
        return [
            {
                "name": name,
                "title": factory.title,
            }
            for name, factory in sorted(ALERT_SERVICES_FACTORIES.items(), key=lambda i: i[1].title.lower())
        ]

    @private
    async def _extend(self, service):
        try:
            service["type__title"] = ALERT_SERVICES_FACTORIES[service["type"]].title
        except KeyError:
            service["type__title"] = "<Unknown>"

        return service

    @private
    async def _compress(self, service):
        service.pop("type__title")

        return service

    @private
    async def _validate(self, service, schema_name):
        verrors = ValidationErrors()

        factory = ALERT_SERVICES_FACTORIES.get(service["type"])
        if factory is None:
            verrors.add(f"{schema_name}.type", "This field has invalid value")
            raise verrors

        verrors.add_child(f"{schema_name}.attributes",
                          validate_attributes(list(factory.schema.attrs.values()), service))

        if verrors:
            raise verrors

    @accepts(Dict(
        "alert_service_create",
        Str("name"),
        Str("type", required=True),
        Dict("attributes", additional_attrs=True),
        Str("level", enum=list(AlertLevel.__members__)),
        Bool("enabled"),
        register=True,
    ))
    async def do_create(self, data):
        """
        Create an Alert Service of specified `type`.

        If `enabled`, it sends alerts to the configured `type` of Alert Service.

        .. examples(websocket)::

          Create an Alert Service of Mail `type`

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "alertservice.create",
                "params": [{
                    "name": "Test Email Alert",
                    "enabled": true,
                    "type": "Mail",
                    "attributes": {
                        "email": "dev@ixsystems.com"
                    },
                    "settings": {
                        "VolumeVersion": "HOURLY"
                    }
                }]
            }
        """
        await self._validate(data, "alert_service_create")

        data["id"] = await self.middleware.call("datastore.insert", self._config.datastore, data)

        await self._extend(data)

        return await self.get_instance(data["id"])

    @accepts(Int("id"), Patch(
        "alert_service_create",
        "alert_service_update",
        ("attr", {"update": True}),
    ))
    async def do_update(self, id, data):
        """
        Update Alert Service of `id`.
        """
        old = await self.middleware.call("datastore.query", self._config.datastore, [("id", "=", id)],
                                         {"extend": self._config.datastore_extend,
                                          "get": True})

        new = old.copy()
        new.update(data)

        await self._validate(new, "alert_service_update")

        await self._compress(new)

        await self.middleware.call("datastore.update", self._config.datastore, id, new)

        return await self.get_instance(id)

    @accepts(Int("id"))
    async def do_delete(self, id):
        """
        Delete Alert Service of `id`.
        """
        return await self.middleware.call("datastore.delete", self._config.datastore, id)

    @accepts(
        Ref('alert_service_create')
    )
    @returns(Bool('successful_test', description='Is `true` if test is successful'))
    async def test(self, data):
        """
        Send a test alert using `type` of Alert Service.

        .. examples(websocket)::

          Send a test alert using Alert Service of Mail `type`.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "alertservice.test",
                "params": [{
                    "name": "Test Email Alert",
                    "enabled": true,
                    "type": "Mail",
                    "attributes": {
                        "email": "dev@ixsystems.com"
                    },
                    "settings": {}
                }]
            }
        """
        await self._validate(data, "alert_service_test")

        factory = ALERT_SERVICES_FACTORIES.get(data["type"])
        if factory is None:
            self.logger.error("Alert service %r does not exist", data["type"])
            return False

        try:
            alert_service = factory(self.middleware, data["attributes"])
        except Exception:
            self.logger.error("Error creating alert service %r with parameters=%r",
                              data["type"], data["attributes"], exc_info=True)
            return False

        master_node = "A"
        if await self.middleware.call("failover.licensed"):
            master_node = await self.middleware.call("failover.node")

        test_alert = Alert(
            TestAlertClass,
            node=master_node,
            datetime=datetime.utcnow(),
            last_occurrence=datetime.utcnow(),
            _uuid="test",
        )

        try:
            await alert_service.send([test_alert], [], [test_alert])
        except Exception:
            self.logger.error("Error in alert service %r", data["type"], exc_info=True)
            return False

        return True


class AlertClassesModel(sa.Model):
    __tablename__ = 'system_alertclasses'

    id = sa.Column(sa.Integer(), primary_key=True)
    classes = sa.Column(sa.JSON())


class AlertClassesService(ConfigService):
    class Config:
        datastore = "system.alertclasses"
        cli_namespace = "system.alert.class"

    ENTRY = Dict(
        "alertclasses_entry",
        Int("id"),
        Dict("classes", additional_attrs=True),
    )

    async def do_update(self, data):
        """
        Update default Alert settings.

        .. examples(rest)::

        Set ClassName's level to LEVEL and policy to POLICY. Reset settings for other alert classes.

        {
            "classes": {
                "ClassName": {
                    "level": "LEVEL",
                    "policy": "POLICY"
                }
            }
        }
        """
        old = await self.config()

        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()

        for k, v in new["classes"].items():
            if k not in AlertClass.class_by_name:
                verrors.add(f"alert_class_update.classes.{k}", "This alert class does not exist")

            if not isinstance(v, dict):
                verrors.add(f"alert_class_update.classes.{k}", "Not a dictionary")

            if "level" in v:
                if v["level"] not in AlertLevel.__members__:
                    verrors.add(f"alert_class_update.classes.{k}.level", "This alert level does not exist")

            if "policy" in v:
                if v["policy"] not in POLICIES:
                    verrors.add(f"alert_class_update.classes.{k}.policy", "This alert policy does not exist")

        if verrors:
            raise verrors

        await self.middleware.call("datastore.update", self._config.datastore, old["id"], new)

        return await self.config()


async def _event_system(middleware, event_type, args):
    if args["id"] == "ready":
        if SEND_ALERTS_ON_READY:
            await middleware.call("alert.send_alerts")


async def setup(middleware):
    middleware.event_register("alert.list", "Sent on alert changes.")

    await middleware.call("alert.load")
    await middleware.call("alert.initialize")

    middleware.event_subscribe("system", _event_system)
