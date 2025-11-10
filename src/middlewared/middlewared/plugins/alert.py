from dataclasses import dataclass
from collections import defaultdict, namedtuple
import copy
from datetime import datetime, timezone
import errno
from itertools import zip_longest
import os
import textwrap
import time
from typing import Any
import uuid

import html2text
from pydantic_core import ValidationError

from truenas_api_client import ReserveFDException

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
    ThreadedAlertSource,
    ThreadedAlertService,
    ProThreadedAlertService,
)
from middlewared.alert.base import UnavailableException, AlertService as _AlertService
from middlewared.api import api_method, Event
from middlewared.api.base import BaseModel
from middlewared.api.current import (
    AlertDismissArgs, AlertDismissResult, AlertListArgs, AlertListResult, AlertListCategoriesArgs,
    AlertListCategoriesResult, AlertListPoliciesArgs, AlertListPoliciesResult, AlertRestoreArgs, AlertRestoreResult,
    AlertClassesEntry, AlertClassesUpdateArgs, AlertClassesUpdateResult, AlertServiceCreateArgs,
    AlertServiceCreateResult, AlertServiceUpdateArgs, AlertServiceUpdateResult, AlertServiceDeleteArgs,
    AlertServiceDeleteResult, AlertServiceTestArgs, AlertServiceTestResult, AlertServiceEntry, AlertListAddedEvent,
    AlertListChangedEvent, AlertListRemovedEvent,
)
from middlewared.service import (
    ConfigService, CRUDService, Service, ValidationErrors,
    job, periodic, private,
)
from middlewared.service_exception import CallError
import middlewared.sqlalchemy as sa
from middlewared.utils import bisect
from middlewared.utils.plugins import load_modules, load_classes
from middlewared.utils.python import get_middlewared_dir
from middlewared.utils.time_utils import utc_now
from middlewared.plugins.failover_.remote import NETWORK_ERRORS

POLICIES = ["IMMEDIATELY", "HOURLY", "DAILY", "NEVER"]
DEFAULT_POLICY = "IMMEDIATELY"
ALERT_SOURCES = {}
ALERT_SERVICES_FACTORIES = {}
SEND_ALERTS_ON_READY = False
# The below value come from observation from support of how long a M-series boot can take.
FAILOVER_ALERTS_BACKOFF_SECS = 900

AlertSourceLock = namedtuple("AlertSourceLock", ["source_name", "expires_at"])


@dataclass(slots=True, frozen=True, kw_only=True)
class AlertFailoverInfo:
    this_node: str
    other_node: str
    run_on_backup_node: bool
    run_failover_related: bool
    stable_peer: bool


class AlertModel(sa.Model):
    __tablename__ = 'system_alert'

    id = sa.Column(sa.Integer(), primary_key=True)
    node = sa.Column(sa.String(100))
    source = sa.Column(sa.Text())
    key = sa.Column(sa.Text())
    datetime = sa.Column(sa.DateTime())
    last_occurrence = sa.Column(sa.DateTime())
    text = sa.Column(sa.Text())
    args = sa.Column(sa.JSON(None))
    dismissed = sa.Column(sa.Boolean())
    uuid = sa.Column(sa.Text())
    klass = sa.Column(sa.Text())


class AlertSourceRunFailedAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.CRITICAL
    title = "Alert Check Failed"
    text = "Failed to check for alert %(source_name)s: %(traceback)s"

    exclude_from_list = True


class AlertSourceRunFailedOnBackupNodeAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.CRITICAL
    title = "Alert Check Failed (Standby Controller)"
    text = "Failed to check for alert %(source_name)s on standby controller: %(traceback)s"

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

    def delete_alert(self, alert):
        self.last_key_value_alerts.pop(alert.uuid, None)


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

    async def get_alert_class(self, alert):
        await self._ensure_initialized()
        return self.classes.get(alert.klass.name, {})

    async def should_show_alert(self, alert):
        await self._ensure_initialized()

        if self.product_type not in alert.klass.products:
            return False

        if (await self.get_alert_class(alert)).get("policy") == "NEVER":
            return False

        return True

    async def _ensure_initialized(self):
        if not self.initialized:
            self.product_type = await self.middleware.call("alert.product_type")
            self.classes = (await self.middleware.call("alertclasses.config"))["classes"]
            self.nodes = await self.middleware.call("alert.node_map")

            self.initialized = True


class AlertOneshotCreateArgs(BaseModel):
    klass: str
    args: Any


class AlertOneshotCreateResult(BaseModel):
    result: None


class AlertOneshotDeleteArgs(BaseModel):
    klass: str | list[str]
    query: Any = None


class AlertOneshotDeleteResult(BaseModel):
    result: None


class AlertService(Service):
    alert_sources_errors = set()

    class Config:
        cli_namespace = "system.alert"
        events = [
            Event(
                name="alert.list",
                description="Sent on alert changes.",
                roles=["ALERT_LIST_READ"],
                models={
                    "ADDED": AlertListAddedEvent,
                    "CHANGED": AlertListChangedEvent,
                    "REMOVED": AlertListRemovedEvent,
                },
            ),
        ]

    def __init__(self, middleware):
        super().__init__(middleware)

        self.blocked_sources = defaultdict(set)
        self.sources_locks = {}

        self.blocked_failover_alerts_until = 0

        self.sources_run_times = defaultdict(lambda: {
            "last": [],
            "max": 0,
            "total_count": 0,
            "total_time": 0,
        })

    @private
    def load(self):
        for module in load_modules(os.path.join(get_middlewared_dir(), "alert", "source")):
            for cls in load_classes(module, AlertSource, (ThreadedAlertSource,)):
                source = cls(self.middleware)
                if source.name in ALERT_SOURCES:
                    raise RuntimeError(f"Alert source {source.name} is already registered")
                ALERT_SOURCES[source.name] = source

    @private
    async def initialize(self, load=True):
        is_enterprise = await self.middleware.call("system.is_enterprise")

        self.node = "A"
        if is_enterprise:
            if await self.middleware.call("failover.node") == "B":
                self.node = "B"

        self.alerts = []
        if load:
            alerts_uuids = set()
            alerts_by_classes = defaultdict(list)
            for alert in await self.middleware.call("datastore.query", "system.alert"):
                del alert["id"]

                if alert["source"] and alert["source"] not in ALERT_SOURCES:
                    self.logger.info("Alert source %r is no longer present", alert["source"])
                    continue

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

                if alert.uuid not in alerts_uuids:
                    alerts_uuids.add(alert.uuid)
                    alerts_by_classes[alert.klass.__name__].append(alert)

            for alerts in alerts_by_classes.values():
                if isinstance(alerts[0].klass, OneShotAlertClass):
                    alerts = await alerts[0].klass.load(alerts)

                self.alerts.extend(alerts)
        else:
            await self.flush_alerts()

        self.alert_source_last_run = defaultdict(lambda: datetime.min)

        self.policies = {
            "IMMEDIATELY": AlertPolicy(),
            "HOURLY": AlertPolicy(lambda d: (d.date(), d.hour)),
            "DAILY": AlertPolicy(lambda d: (d.date())),
            "NEVER": AlertPolicy(lambda d: None),
        }
        for policy in self.policies.values():
            policy.receive_alerts(utc_now(), self.alerts)

    @private
    async def terminate(self):
        await self.flush_alerts()

    @api_method(AlertListPoliciesArgs, AlertListPoliciesResult, roles=['ALERT_LIST_READ'])
    async def list_policies(self):
        """
        List all alert policies which indicate the frequency of the alerts.
        """
        return POLICIES

    @api_method(AlertListCategoriesArgs, AlertListCategoriesResult, roles=['ALERT_LIST_READ'])
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
                            "proactive_support": alert_class.proactive_support,
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

    @api_method(AlertListArgs, AlertListResult, roles=['ALERT_LIST_READ'])
    async def list(self):
        """
        List all types of alerts including active/dismissed currently in the system.
        """

        as_ = AlertSerializer(self.middleware)
        classes = (await self.middleware.call("alertclasses.config"))["classes"]

        return [
            await as_.serialize(alert)
            for alert in sorted(
                self.alerts,
                key=lambda alert: (
                    -get_alert_level(alert, classes).value,
                    alert.klass.title,
                    alert.datetime,
                ),
            )
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

    @api_method(AlertDismissArgs, AlertDismissResult, roles=['ALERT_LIST_WRITE'])
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
        try:
            self.alerts.remove(alert)
            removed = True
        except ValueError:
            removed = False

        for policy in self.policies.values():
            policy.delete_alert(alert)

        if removed:
            self._send_alert_deleted_event(alert)

    @api_method(AlertRestoreArgs, AlertRestoreResult, roles=['ALERT_LIST_WRITE'])
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
        self.middleware.send_event("alert.list", "REMOVED", id=alert.uuid)

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

        now = utc_now()
        for policy_name, policy in self.policies.items():
            gone_alerts, new_alerts = policy.receive_alerts(now, self.alerts)

            for alert_service_desc in await self.middleware.call("alertservice.query", [["enabled", "=", True]]):
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

                factory = ALERT_SERVICES_FACTORIES[alert_service_desc["attributes"]["type"]]
                alert_service = factory(self.middleware, alert_service_desc["attributes"])

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
                    gone_proactive_support_alerts = [
                        alert
                        for alert in gone_alerts
                        if (
                            alert.klass.proactive_support and
                            (await as_.get_alert_class(alert)).get("proactive_support", True) and
                            alert.klass.proactive_support_notify_gone
                        )
                    ]
                    new_proactive_support_alerts = [
                        alert
                        for alert in new_alerts
                        if (
                            alert.klass.proactive_support and
                            (await as_.get_alert_class(alert)).get("proactive_support", True)
                        )
                    ]
                    if gone_proactive_support_alerts or new_proactive_support_alerts:
                        if await self.middleware.call("support.is_available_and_enabled"):
                            support = await self.middleware.call("support.config")

                            msg = []
                            if gone_proactive_support_alerts:
                                msg.append("The following alerts were cleared:")
                                msg += [f"* {html2text.html2text(alert.formatted)}"
                                        for alert in gone_proactive_support_alerts]
                            if new_proactive_support_alerts:
                                msg.append("The following new alerts appeared:")
                                msg += [f"* {html2text.html2text(alert.formatted)}"
                                        for alert in new_proactive_support_alerts]

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

    async def __get_failover_info(self):
        this_node, other_node = "A", "B"
        run_on_backup_node = run_failover_related = stable_peer = False
        run_failover_related = await self.middleware.call("failover.licensed")
        if run_failover_related:
            if await self.middleware.call("failover.node") != "A":
                this_node, other_node = "B", "A"

            run_failover_related = time.monotonic() > self.blocked_failover_alerts_until
            if run_failover_related:
                args = ([], {"connect_timeout": 2})

                # Do not run on backup if there is a software version mismatch
                try:
                    rem_ver = await self.middleware.call("failover.call_remote", "system.version", *args)
                    run_on_backup_node = (await self.middleware.call("system.version")) == rem_ver
                except Exception:
                    pass

                # Do not run on backup if the other node is not READY
                if run_on_backup_node:
                    try:
                        run_on_backup_node = (await self.middleware.call(
                            "failover.call_remote", "system.state", *args
                        )) == "READY"
                    except Exception:
                        pass

                # Do not run on backup if the other node is not BACKUP
                if run_on_backup_node:
                    try:
                        run_on_backup_node = (await self.middleware.call(
                            "failover.call_remote", "system.status", *args
                        )) == "BACKUP"
                    except Exception:
                        pass

                # Maintain a flag indicating whether the failover
                # node is stable (has been booted for long enough).
                try:
                    stable_peer = (await self.middleware.call(
                        "failover.call_remote", "system.time_info", *args
                    ))['uptime_seconds'] > FAILOVER_ALERTS_BACKOFF_SECS
                except Exception:
                    pass

        return AlertFailoverInfo(
            this_node=this_node,
            other_node=other_node,
            run_on_backup_node=run_on_backup_node,
            run_failover_related=run_failover_related,
            stable_peer=stable_peer
        )

    async def __handle_locked_alert_source(self, name, this_node, other_node):
        this_node_alerts, other_node_alerts = [], []
        locked = self.blocked_sources[name]
        if locked:
            self.logger.debug("Not running alert source %r because it is blocked", name)
            for i in filter(lambda x: x.source == name, self.alerts):
                if i.node == this_node:
                    this_node_alerts.append(i)
                elif i.node == other_node:
                    other_node_alerts.append(i)
        return this_node_alerts, other_node_alerts, locked

    async def __run_other_node_alert_source(self, name):
        keys = ("args", "datetime", "last_occurrence", "dismissed", "mail",)
        other_node_alerts = []
        try:
            try:
                for alert in await self.middleware.call("failover.call_remote", "alert.run_source", [name]):
                    other_node_alerts.append(
                        Alert(**dict(
                            {k: v for k, v in alert.items() if k in keys},
                            klass=AlertClass.class_by_name[alert["klass"]],
                            _source=alert["source"],
                            _key=alert["key"]
                        ))
                    )
            except CallError as e:
                if e.errno not in NETWORK_ERRORS + (CallError.EALERTCHECKERUNAVAILABLE,):
                    raise
        except ReserveFDException:
            self.logger.debug('Failed to reserve a privileged port')
        except Exception as e:
            other_node_alerts = [Alert(
                AlertSourceRunFailedOnBackupNodeAlertClass,
                args={"source_name": name, "traceback": str(e)},
                _source=name
            )]

        return other_node_alerts

    async def __run_alerts(self):
        product_type = await self.middleware.call("alert.product_type")
        fi = await self.__get_failover_info()
        for k, source_lock in list(self.sources_locks.items()):
            if source_lock.expires_at <= time.monotonic():
                await self.unblock_source(k)

        for alert_source in ALERT_SOURCES.values():
            if product_type not in alert_source.products:
                continue

            if alert_source.failover_related and not fi.run_failover_related:
                continue

            if alert_source.require_stable_peer and not fi.stable_peer:
                continue

            if not alert_source.schedule.should_run(utc_now(), self.alert_source_last_run[alert_source.name]):
                continue

            self.alert_source_last_run[alert_source.name] = utc_now()

            this_node_alerts, other_node_alerts, locked = await self.__handle_locked_alert_source(
                alert_source.name, fi.this_node, fi.other_node
            )
            if not locked:
                self.logger.trace("Running alert source: %r", alert_source.name)
                try:
                    this_node_alerts = await self.__run_source(alert_source.name)
                except UnavailableException:
                    pass

                if fi.run_on_backup_node and alert_source.run_on_backup_node:
                    other_node_alerts = await self.__run_other_node_alert_source(alert_source.name)

            for talert, oalert in zip_longest(this_node_alerts, other_node_alerts, fillvalue=None):
                if talert is not None:
                    talert.node = fi.this_node
                    self.__handle_alert(talert)
                if oalert is not None:
                    oalert.node = fi.other_node
                    self.__handle_alert(oalert)

            self.alerts = (
                [a for a in self.alerts if a.source != alert_source.name] + this_node_alerts + other_node_alerts
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
            alert.datetime = alert.datetime or utc_now()
            if alert.datetime.tzinfo is not None:
                alert.datetime = alert.datetime.astimezone(timezone.utc).replace(tzinfo=None)
        else:
            alert.datetime = existing_alert.datetime
        alert.last_occurrence = utc_now()
        if existing_alert is None:
            alert.dismissed = False
        else:
            alert.dismissed = existing_alert.dismissed

    def __expire_alerts(self):
        self.alerts = list(filter(lambda alert: not self.__should_expire_alert(alert), self.alerts))

    def __should_expire_alert(self, alert):
        if issubclass(alert.klass, OneShotAlertClass):
            if alert.klass.expires_after is not None:
                return alert.last_occurrence < utc_now() - alert.klass.expires_after

        return False

    @private
    async def sources_stats(self):
        return {
            k: {"avg": v["total_time"] / v["total_count"] if v["total_count"] != 0 else 0, **v}
            for k, v in sorted(self.sources_run_times.items(), key=lambda t: t[0])
        }

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
        self.blocked_failover_alerts_until = time.monotonic() + FAILOVER_ALERTS_BACKOFF_SECS

    async def __run_source(self, source_name):
        alert_source = ALERT_SOURCES[source_name]

        start = time.monotonic()
        try:
            alerts = (await alert_source.check()) or []
        except UnavailableException:
            raise
        except Exception as e:
            if source_name not in self.alert_sources_errors:
                self.logger.error("Error checking for alert %r", alert_source.name, exc_info=True)
                self.alert_sources_errors.add(source_name)

            alerts = [
                Alert(AlertSourceRunFailedAlertClass,
                      args={
                          "source_name": alert_source.name,
                          "traceback": str(e),
                      })
            ]
        else:
            self.alert_sources_errors.discard(source_name)
            if not isinstance(alerts, list):
                alerts = [alerts]
        finally:
            run_time = time.monotonic() - start
            source_stat = self.sources_run_times[source_name]
            source_stat["last"] = source_stat["last"][-9:] + [run_time]
            source_stat["max"] = max(source_stat["max"], run_time)
            source_stat["total_count"] += 1
            source_stat["total_time"] += run_time

        keys = set()
        unique_alerts = []
        for alert in alerts:
            if alert.key in keys:
                continue

            keys.add(alert.key)
            unique_alerts.append(alert)
        alerts = unique_alerts

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

    @api_method(AlertOneshotCreateArgs, AlertOneshotCreateResult, private=True)
    @job(
        lock="process_alerts",
        lock_queue_size=None,  # Must be `None` so that alert operations are not discarded
        transient=True,
    )
    async def oneshot_create(self, job, klass, args):
        """
        Creates a one-shot alert of specified `klass`, passing `args` to `klass.create` method.

        Normal alert creation logic will be applied, so if you create an alert with the same `key` as an already
        existing alert, no duplicate alert will be created.

        :param klass: one-shot alert class name (without the `AlertClass` suffix).
        :param args: `args` that will be passed to `klass.create` method.
        """

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

    @api_method(AlertOneshotDeleteArgs, AlertOneshotDeleteResult, private=True)
    @job(
        lock="process_alerts",
        lock_queue_size=None,  # Must be `None` so that alert operations are not discarded
        transient=True,
    )
    async def oneshot_delete(self, job, klass, query):
        """
        Deletes one-shot alerts of specified `klass` or klasses, passing `query`
        to `klass.delete` method.

        It's not an error if no alerts matching delete `query` exist.

        :param klass: either one-shot alert class name (without the `AlertClass` suffix), or list thereof.
        :param query: `query` that will be passed to `klass.delete` method.
        """

        if isinstance(klass, list):
            klasses = klass
        else:
            klasses = [klass]

        deleted = False
        for klassname in klasses:
            try:
                klass = AlertClass.class_by_name[klassname]
            except KeyError:
                raise CallError(f"Invalid alert source: {klassname!r}")

            if not issubclass(klass, OneShotAlertClass):
                raise CallError(f"Alert class {klassname!r} is not a one-shot alert source")

            related_alerts, unrelated_alerts = bisect(lambda a: (a.node, a.klass) == (self.node, klass),
                                                      self.alerts)
            left_alerts = await klass(self.middleware).delete(related_alerts, query)
            for deleted_alert in related_alerts:
                if deleted_alert not in left_alerts:
                    self.alerts.remove(deleted_alert)
                    deleted = True

        if deleted:
            # We need to flush alerts to the database immediately after deleting oneshot alerts.
            # Some oneshot alerts can only de deleted programmatically (i.e. cloud sync oneshot alerts are deleted
            # when deleting cloud sync task). If we delete a cloud sync task and then reboot the system abruptly,
            # the alerts won't be flushed to the database and on next boot an alert for nonexisting cloud sync task
            # will appear, and it won't be deletable.
            await self.middleware.call("alert.flush_alerts")

            await self.middleware.call("alert.send_alerts")

    @private
    def alert_source_clear_run(self, name):
        """
        Mark the alert source as never ran so that it will be re-run within the next minute.
        This is useful when you know some alert conditions were just changed.

        :param name: alert source name (without `AlertClass` suffix)
        """
        alert_source = ALERT_SOURCES.get(name)
        if not alert_source:
            raise CallError(f"Alert source {name!r} not found.", errno.ENOENT)

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
        datastore_extend = "alertservice.extend"
        datastore_order_by = ["name"]
        cli_namespace = "system.alert.service"
        entry = AlertServiceEntry
        role_prefix = 'ALERT'

    @private
    async def extend(self, service):
        service["attributes"]["type"] = service.pop("type")

        try:
            service["type__title"] = ALERT_SERVICES_FACTORIES[service["attributes"]["type"]].title
        except KeyError:
            service["type__title"] = "<Unknown>"

        return service

    async def _compress(self, service):
        service["type"] = service["attributes"].pop("type")
        service.pop("type__title", None)
        return service

    async def _validate(self, service, schema_name):
        verrors = ValidationErrors()

        levels = AlertLevel.__members__
        if service["level"] not in levels:
            verrors.add(f"{schema_name}.level", f"Level must be one of {list(levels)}")

        verrors.check()

    @api_method(AlertServiceCreateArgs, AlertServiceCreateResult)
    async def do_create(self, data):
        """
        Create an Alert Service of specified `type`.

        If `enabled`, it sends alerts to the configured `type` of Alert Service.
        """
        await self._validate(data, "alert_service_create")

        await self._compress(data)

        data["id"] = await self.middleware.call("datastore.insert", self._config.datastore, data)

        return await self.get_instance(data["id"])

    @api_method(AlertServiceUpdateArgs, AlertServiceUpdateResult)
    async def do_update(self, id_, data):
        """
        Update Alert Service of `id`.
        """
        old = await self.middleware.call("datastore.query", self._config.datastore, [("id", "=", id_)],
                                         {"extend": self._config.datastore_extend,
                                          "get": True})

        new = old.copy()
        new.update(data)

        await self._validate(new, "alert_service_update")

        await self._compress(new)

        await self.middleware.call("datastore.update", self._config.datastore, id_, new)

        return await self.get_instance(id_)

    @api_method(AlertServiceDeleteArgs, AlertServiceDeleteResult)
    async def do_delete(self, id_):
        """
        Delete Alert Service of `id`.
        """
        return await self.middleware.call("datastore.delete", self._config.datastore, id_)

    @api_method(AlertServiceTestArgs, AlertServiceTestResult, roles=['ALERT_WRITE'])
    async def test(self, data):
        """
        Send a test alert using `type` of Alert Service.
        """
        await self._validate(data, "alert_service_test")

        factory = ALERT_SERVICES_FACTORIES[data["attributes"]["type"]]
        alert_service = factory(self.middleware, data["attributes"])

        master_node = "A"
        if await self.middleware.call("failover.licensed"):
            master_node = await self.middleware.call("failover.node")

        test_alert = Alert(
            TestAlertClass,
            node=master_node,
            datetime=utc_now(),
            last_occurrence=utc_now(),
            _uuid=str(uuid.uuid4()),
        )

        try:
            await alert_service.send([test_alert], [], [test_alert])
        except Exception:
            self.logger.error("Error in alert service %r", data["type"], exc_info=True)
            return False

        return True

    @private
    def load(self):
        for module in load_modules(
            os.path.join(os.path.dirname(os.path.realpath(__file__)), os.path.pardir, "alert", "service")
        ):
            for cls in load_classes(module, _AlertService, (ThreadedAlertService, ProThreadedAlertService)):
                ALERT_SERVICES_FACTORIES[cls.name()] = cls

    @private
    async def initialize(self):
        for alertservice in await self.middleware.call("datastore.query", "system.alertservice"):
            if alertservice["type"] not in ALERT_SERVICES_FACTORIES:
                self.logger.debug("Removing obsolete alert service %r (%r)", alertservice["name"], alertservice["type"])
                await self.middleware.call("datastore.delete", "system.alertservice", alertservice["id"])
                continue

            try:
                AlertServiceEntry.model_validate(await self.extend(copy.deepcopy(alertservice)))
            except ValidationError as e:
                attributes = copy.copy(alertservice["attributes"])
                for error in e.errors():
                    if (
                        error["type"] == "extra_forbidden" and
                        len(error["loc"]) == 3 and
                        error["loc"][0] == "attributes"
                    ):
                        # If we remove some attributes, it should not be an error if they are still left in the database
                        attribute = error["loc"][2]
                        attributes.pop(attribute, None)
                        self.logger.debug(
                            "Removing obsolete attribute %r for alert service %r (%r)",
                            attribute,
                            alertservice["name"],
                            alertservice["type"],
                        )
                    else:
                        self.logger.debug(
                            "Unknown validaton error for alert service %r (%r): %r. Removing it completely",
                            alertservice["name"],
                            alertservice["type"],
                            error,
                        )
                        await self.middleware.call("datastore.delete", "system.alertservice", alertservice["id"])
                        break
                else:
                    await self.middleware.call("datastore.update", "system.alertservice", alertservice["id"], {
                        "attributes": attributes,
                    })


class AlertClassesModel(sa.Model):
    __tablename__ = 'system_alertclasses'

    id = sa.Column(sa.Integer(), primary_key=True)
    classes = sa.Column(sa.JSON())


class AlertClassesService(ConfigService):
    class Config:
        datastore = "system.alertclasses"
        cli_namespace = "system.alert.class"
        entry = AlertClassesEntry
        role_prefix = 'ALERT'

    @api_method(AlertClassesUpdateArgs, AlertClassesUpdateResult)
    async def do_update(self, data):
        """
        Update default Alert settings.

        .. examples(rest)::

        Set ClassName's level to LEVEL and policy to POLICY. Reset settings for other alert classes.

        {
            "classes": {
                "ClassName": {
                    "level": "LEVEL",
                    "policy": "POLICY",
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
                continue

            if "proactive_support" in v and not AlertClass.class_by_name[k].proactive_support:
                verrors.add(
                    f"alert_class_update.classes.{k}.proactive_support",
                    "Proactive support is not supported by this alert class",
                )

        verrors.check()

        await self.middleware.call("datastore.update", self._config.datastore, old["id"], new)

        return await self.config()


async def _event_system(middleware, event_type, args):
    if SEND_ALERTS_ON_READY:
        await middleware.call("alert.send_alerts")


async def setup(middleware):
    await middleware.call("alertservice.load")
    await middleware.call("alertservice.initialize")

    await middleware.call("alert.load")
    await middleware.call("alert.initialize")

    middleware.event_subscribe("system.ready", _event_system)
