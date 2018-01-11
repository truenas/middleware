from collections import defaultdict
import copy
from datetime import datetime
import json
import os
import traceback

from freenasUI.common.system import get_sw_version
from freenasUI.support.utils import get_license
from licenselib.license import ContractType

from middlewared.alert.base import *
from middlewared.alert.base import AlertService as _AlertService
from middlewared.schema import Dict, Str, Bool, Int, accepts, Patch
from middlewared.service import (
    ConfigService, CRUDService, Service, ValidationErrors,
    periodic, private,
)
from middlewared.utils import load_modules, load_classes

POLICIES = ["IMMEDIATELY", "HOURLY", "DAILY", "NEVER"]
DEFAULT_POLICY = "IMMEDIATELY"

alert_sources = []
alert_services_factories = {}


class AlertPolicy:
    def __init__(self, key=lambda now: now):
        self.key = key

        self.last_key_value = None
        self.last_key_value_alerts = defaultdict(dict)

    def receive_alerts(self, now, alerts):
        gone_alerts = []
        new_alerts = []
        key = self.key(now)
        if key != self.last_key_value:
            for alert_source_name in set(alerts.keys()) | set(self.last_key_value_alerts.keys()):
                for gone_alert in (set(self.last_key_value_alerts[alert_source_name].keys()) -
                                   set(alerts[alert_source_name].keys())):
                    gone_alerts.append(self.last_key_value_alerts[alert_source_name][gone_alert])
                for new_alert in (set(alerts[alert_source_name].keys()) -
                                  set(self.last_key_value_alerts[alert_source_name].keys())):
                    new_alerts.append(alerts[alert_source_name][new_alert])

            self.last_key_value = key
            self.last_key_value_alerts = copy.deepcopy(alerts)

        return gone_alerts, new_alerts


class AlertService(Service):
    def __init__(self, middleware):
        super().__init__(middleware)

        self.node = "A"

        self.alerts = defaultdict(dict)

        self.alert_source_last_run = defaultdict(lambda: datetime.min)

        self.policies = {
            "IMMEDIATELY": AlertPolicy(),
            "HOURLY": AlertPolicy(lambda d: (d.date(), d.hour)),
            "DAILY": AlertPolicy(lambda d: (d.date())),
            "NEVER": AlertPolicy(lambda d: None),
        }

    @private
    async def initialize(self):
        if not await self.middleware.call("system.is_freenas"):
            if await self.middleware.call("notifier.failover_node") == "B":
                self.node = "B"

        for alert in await self.middleware.call("datastore.query", "system.alert", [("node", "=", self.node)]):
            del alert["id"]
            del alert["node"]
            alert["level"] = AlertLevel(alert["level"])

            alert = Alert(**alert)

            self.alerts[alert.source][alert.key] = alert

        for policy in self.policies.values():
            policy.receive_alerts(datetime.utcnow(), self.alerts)

        for module in load_modules(os.path.join(os.path.dirname(os.path.realpath(__file__)), os.path.pardir,
                                                "alert", "source")):
            for cls in load_classes(module, AlertSource, (FilePresenceAlertSource, ThreadedAlertSource)):
                alert_sources.append(cls(self.middleware))

        for module in load_modules(os.path.join(os.path.dirname(os.path.realpath(__file__)), os.path.pardir,
                                                "alert", "service")):
            for cls in load_classes(module, _AlertService, (ThreadedAlertService,)):
                alert_services_factories[cls.name()] = cls

    async def terminate(self):
        await self.flush_alerts()

    async def list_policies(self):
        return POLICIES

    async def list_sources(self):
        return [
            {
                "name": source.name,
                "title": source.title,
            }
            for source in sorted(alert_sources, key=lambda source: source.title.lower())
        ]

    def list(self):
        return [
            dict(alert.__dict__,
                 id=f"{alert.source};{alert.key}",
                 level=alert.level.name,
                 formatted=alert.formatted)
            for alert in sorted(sum([list(v.values()) for v in self.alerts.values()], []),
                                key=lambda alert: alert.title)
        ]

    @accepts(Str("id"))
    def dismiss(self, id):
        source, key = id.split(";", 1)
        alert = self.alerts[source][key]
        alert.dismissed = True

    @accepts(Str("id"))
    def restore(self, id):
        source, key = id.split(";", 1)
        alert = self.alerts[source][key]
        alert.dismissed = False

    @periodic(60)
    async def process_alerts(self):
        await self.__run_alerts()

        default_settings = (await self.middleware.call("alertdefaultsettings.config"))["settings"]

        all_alerts = sum([list(v.values()) for v in self.alerts.values()], [])

        now = datetime.now()
        for policy_name, policy in self.policies.items():
            gone_alerts, new_alerts = policy.receive_alerts(now, self.alerts)

            for alert_service_desc in await self.middleware.call("datastore.query", "system.alertservice"):
                service_settings = dict(default_settings, **alert_service_desc["settings"])

                service_gone_alerts = [alert for alert in gone_alerts
                                       if service_settings.get(alert.source, DEFAULT_POLICY) == policy_name]
                service_new_alerts = [alert for alert in new_alerts
                                      if service_settings.get(alert.source, DEFAULT_POLICY) == policy_name]

                if not service_gone_alerts and not service_new_alerts:
                    continue

                factory = alert_services_factories.get(alert_service_desc["type"])
                if factory is None:
                    self.logger.error("Alert service %r does not exist", alert_service_desc["type"])
                    continue

                try:
                    alert_service = factory(self.middleware, alert_service_desc["attributes"])
                except Exception:
                    self.logger.error("Error creating alert service %r with parameters=%r",
                                      alert_service_desc["type"], alert_service_desc["attributes"], exc_info=True)
                    continue

                if all_alerts or service_gone_alerts or service_new_alerts:
                    try:
                        await alert_service.send(all_alerts, service_gone_alerts, service_new_alerts)
                    except Exception:
                        self.logger.error("Error in alert service %r", alert_service_desc["type"], exc_info=True)

            if policy_name == "IMMEDIATELY":
                if not await self.middleware.call("system.is_freenas"):
                    new_hardware_alerts = [alert for alert in new_alerts if alert_sources[alert.source].hardware]
                    if new_hardware_alerts:
                        license = get_license()
                        if license and license.contract_type in [ContractType.silver.value, ContractType.gold.value]:
                            try:
                                support = await self.middleware.call("datastore.query", "system.support", None,
                                                                     {"get": True})
                            except IndexError:
                                await self.middleware.call("datastore.insert", "system.support", {})

                                support = await self.middleware.call("datastore.query", "system.support", None,
                                                                     {"get": True})

                            if support["enabled"]:
                                msg = [f"* {alert.formatted}" for alert in new_hardware_alerts]

                                serial = await self.middleware.call("system._serial")

                                company = license.customer_name.decode()

                                for name, verbose_name in (
                                    ("name", "Contact Name"),
                                    ("title", "Contact Title"),
                                    ("email", "Contact E-mail"),
                                    ("phone", "Contact Phone"),
                                    ("secondary_name", "Secondary Contact Name"),
                                    ("secondary_title", "Secondary Contact Title"),
                                    ("secondary_email", "Secondary Contact E-mail"),
                                    ("secondary_phone", "Secondary Contact Phone"),
                                ):
                                    value = getattr(support, name)
                                    if value:
                                        msg += ["", "{}: {}".format(verbose_name, value)]

                                try:
                                    await self.middleware.call("support.new_ticket", {
                                        "title": "Automatic alert (%s)" % serial,
                                        "body": "\n".join(msg),
                                        "version": get_sw_version().split("-", 1)[-1],
                                        "debug": False,
                                        "company": company,
                                        "serial": serial,
                                        "department": 20,
                                        "category": "Hardware",
                                        "criticality": "Loss of Functionality",
                                        "environment": "Production",
                                        "name": "Automatic Alert",
                                        "email": "auto-support@ixsystems.com",
                                        "phone": "-",
                                    })
                                except Exception:
                                    self.logger.error(f"Failed to create a support ticket", exc_info=True)

    async def __run_alerts(self):
        for alert_source in alert_sources:
            if datetime.utcnow() < self.alert_source_last_run[alert_source.name] + alert_source.interval:
                continue

            self.alert_source_last_run[alert_source.name] = datetime.utcnow()

            self.logger.trace("Running alert source: %r", alert_source.name)
            try:
                alerts = (await alert_source.check()) or []
            except Exception:
                alerts = [
                    Alert(title="Unable to run alert source %(source_name)r\n%(traceback)s",
                          args={
                              "source_name": alert_source.name,
                              "traceback": traceback.format_exc(),
                          },
                          key="__unhandled_exception__",
                          level=AlertLevel.CRITICAL)
                ]
            else:
                if not isinstance(alerts, list):
                    alerts = [alerts]

            for alert in alerts:
                existing_alert = self.alerts[alert_source.name].get(alert.key)

                alert.source = alert_source.name
                alert.key = alert.key or json.dumps(alert.args, sort_keys=True)
                if existing_alert is None:
                    alert.datetime = datetime.utcnow()
                else:
                    alert.datetime = existing_alert.datetime
                alert.level = alert.level or alert_source.level
                alert.title = alert.title or alert_source.title
                if existing_alert is None:
                    alert.dismissed = False
                else:
                    alert.dismissed = existing_alert.dismissed

            self.alerts[alert_source.name] = {alert.key: alert for alert in alerts}

    @periodic(3600)
    async def flush_alerts(self):
        await self.middleware.call("datastore.sql", "DELETE FROM system_alert WHERE node = %s", (self.node,))

        for alert in sum([list(v.values()) for v in self.alerts.values()], []):
            d = alert.__dict__.copy()
            d["node"] = self.node
            d["level"] = d["level"].value
            await self.middleware.call("datastore.insert", "system.alert", d)


class AlertServiceService(CRUDService):
    class Config:
        datastore = "system.alertservice"
        datastore_extend = "alertservice._extend"
        datastore_order_by = ["name"]

    async def list_types(self):
        return [
            {
                "name": name,
                "title": factory.title,
            }
            for name, factory in sorted(alert_services_factories.items(), key=lambda i: i[1].title.lower())
        ]

    @private
    async def _extend(self, service):
        try:
            service["type__title"] = alert_services_factories[service["type"]].title
        except KeyError:
            service["type__title"] = "<Unknown>"

        return service

    @private
    async def _compress(self, service):
        return service

    @private
    async def _validate(self, service, schema_name):
        verrors = ValidationErrors()

        factory = alert_services_factories.get(service["type"])
        if factory is None:
            verrors.add(f"{schema_name}.type", "This field has invalid value")

        try:
            factory.validate(service["attributes"])
        except ValidationErrors as e:
            verrors.add_child(f"{schema_name}.attributes", e)

        validate_settings(verrors, f"{schema_name}.settings", service["settings"])

        if verrors:
            raise verrors

    @accepts(Dict(
        "alert_service_create",
        Str("name"),
        Str("type"),
        Dict("attributes", additional_attrs=True),
        Bool("enabled"),
        Dict("settings", additional_attrs=True),
        register=True,
    ))
    async def do_create(self, data):
        await self._validate(data, "alert_service_create")

        data["id"] = await self.middleware.call("datastore.insert", self._config.datastore, data)

        await self._extend(data)

        return data

    @accepts(Int("id"), Patch(
        "alert_service_create",
        "alert_service_update",
        ("attr", {"update": True}),
    ))
    async def do_update(self, id, data):
        old = await self.middleware.call("datastore.query", self._config.datastore, [("id", "=", id)],
                                         {"extend": self._config.datastore_extend,
                                          "get": True})

        new = old.copy()
        new.update(data)

        await self._validate(data, "alert_service_update")

        await self._compress(data)

        await self.middleware.call("datastore.update", self._config.datastore, id, data)

        await self._extend(new)

        return new

    @accepts(Int("id"))
    async def do_delete(self, id):
        return await self.middleware.call("datastore.delete", self._config.datastore, id)

    @accepts(Patch(
        "alert_service_create",
        "alert_service_test",
        ("attr", {"update": True}),
    ))
    async def test(self, data):
        await self._validate(data, "alert_service_test")

        factory = alert_services_factories.get(data["type"])
        if factory is None:
            self.logger.error("Alert service %r does not exist", data["type"])
            return False

        try:
            alert_service = factory(self.middleware, data["attributes"])
        except Exception:
            self.logger.error("Error creating alert service %r with parameters=%r",
                              data["type"], data["attributes"], exc_info=True)
            return False

        test_alert = Alert(
            title="Test alert",
            datetime=datetime.utcnow(),
            level=AlertLevel.INFO,
        )

        try:
            await alert_service.send([test_alert], [], [test_alert])
        except Exception:
            self.logger.error("Error in alert service %r", data["type"], exc_info=True)
            return False

        return True


class AlertDefaultSettingsService(ConfigService):
    class Config:
        datastore = "system.alertdefaultsettings"

    @private
    async def _validate(self, settings, schema_name):
        verrors = ValidationErrors()

        validate_settings(verrors, f"{schema_name}.settings", settings["settings"])

        if verrors:
            raise verrors

    @accepts(Dict(
        "alert_default_settings_update",
        Dict("settings", additional_attrs=True),
    ))
    async def do_update(self, data):
        old = await self.config()

        new = old.copy()
        new.update(data)

        await self._validate(data, "alert_default_settings_update")

        await self.middleware.call("datastore.update", self._config.datastore, old["id"], new)

        return new


async def setup(middleware):
    await middleware.call("alert.initialize")


def validate_settings(verrors, schema_name, settings):
    for k, v in settings.items():
        if not any(alert_source.name == k for alert_source in alert_sources):
            verrors.add(f"{schema_name}.{k}", "This alert source does not exist")

        if v not in POLICIES:
            verrors.add(f"{schema_name}.{k}", "This alert policy does not exist")
