"""A runnable `AlertService` for the tests that drive its run loop.

Not `test_`-prefixed, so pytest does not collect it.

`AlertService.__init__` sets none of `alerts`, `node`, `policies` or `alert_source_last_run` --
only `initialize()` does, and that needs a live middleware. Everything here exists to supply
those four the way `initialize()` would, and to make the run loop's side effects observable.

Nothing here defines an `AlertClass` subclass. `AlertClassMeta` registers one into a global
registry at class-definition time, so a stub class would permanently change what the frozen
inventory and the black-hole check iterate over. `AlertSource` has no metaclass and is safe to
subclass.
"""

from collections import defaultdict
from datetime import datetime

from truenas_pylicensed import LicenseType

from middlewared.alert.base import Alert, AlertSource
from middlewared.plugins import alert as alert_plugin
from middlewared.plugins.alert import ALERT_SOURCES, AlertPolicy, AlertService
from middlewared.pytest.unit.entitlements import make_license
from middlewared.utils.entitlements import EntitlementFacts
from middlewared.utils.hardware import HardwareClass
from middlewared.utils.time_utils import utc_now

UNLICENSED = EntitlementFacts(hardware_class=HardwareClass.TRUENAS_HW, license=None)
LICENSED = EntitlementFacts(hardware_class=HardwareClass.TRUENAS_HW, license=make_license(model="M50"))
HA_LICENSED_FACTS = EntitlementFacts(
    hardware_class=HardwareClass.TRUENAS_HW,
    license=make_license(model="M50", type_=LicenseType.ENTERPRISE_HA),
)


class RecordingLogger:
    def __init__(self):
        self.errors = []

    def error(self, message, *args, **kwargs):
        self.errors.append(message % args if args else message)

    def debug(self, *args, **kwargs):
        pass

    def trace(self, *args, **kwargs):
        pass


class RunStubMiddleware:
    """Answers the one question the run loop asks, and refuses everything else.

    The refusal is the point: a run that starts reaching for the datastore or the peer has left
    the path these tests describe, and should say so rather than quietly get a `Mock`.
    """

    def __init__(self):
        self.calls = []

    def event_register(self, *args, **kwargs):
        pass

    def send_event(self, *args, **kwargs):
        pass

    async def run_in_thread(self, fn, *args, **kwargs):
        return fn(*args, **kwargs)

    async def call(self, method, *args, **kwargs):
        self.calls.append(method)
        if method == "failover.licensed":
            return False

        raise AssertionError(f"unexpected call {method!r}")


class RecordingPolicy(AlertPolicy):
    """An `AlertPolicy` that remembers the uuid of every alert deleted through it.

    Purging the alerts of a source that stopped applying leaves `self.alerts` correct whether or
    not the policies were told, so the policy half of that purge is observable only from here.
    """

    def __init__(self, key=lambda now: now):
        super().__init__(key)

        self.deleted = []

    def delete_alert(self, alert):
        self.deleted.append(alert.uuid)
        super().delete_alert(alert)


class AlertRuntime:
    """An `AlertService` whose run loop can be driven, plus the levers a test needs.

    The facts are read through a holder rather than bound once, because a licence upload is the
    one thing that changes them under a running daemon and the purge behaviour only shows up
    across such a change.
    """

    def __init__(self, service, facts_holder):
        self.service = service
        self._facts_holder = facts_holder

    @property
    def alerts(self):
        return self.service.alerts

    @property
    def policies(self):
        return self.service.policies

    def set_alerts(self, *alerts):
        self.service.alerts = list(alerts)

    def set_facts(self, facts):
        """Point the service at new facts, as a licence upload does.

        Clearing `_applicability` as well: `applicability()` holds any reading whose licence is
        not `None`, so a new set of facts is invisible until the held one is dropped. Production
        drops it from `system.post_license_update`.
        """
        self._facts_holder["facts"] = facts
        self.service._applicability = None

    def seed_policies(self):
        """Tell the policies about the alerts the service starts with, as `initialize()` does."""
        for policy in self.service.policies.values():
            policy.receive_alerts(utc_now(), self.service.alerts)

    async def run(self):
        await AlertService._AlertService__run_alerts(self.service)


def make_runtime_service(monkeypatch, facts) -> AlertRuntime:
    facts_holder = {"facts": facts}
    monkeypatch.setattr(alert_plugin, "get_facts", lambda: facts_holder["facts"])
    monkeypatch.setattr(alert_plugin, "_REPORTED_INAPPLICABLE_CLASSES", set())
    # A class attribute, so it outlives the service and has to be replaced on the class.
    monkeypatch.setattr(AlertService, "alert_sources_errors", set())

    service = AlertService(RunStubMiddleware())
    service.logger = RecordingLogger()
    service.node = "A"
    service.alerts = []
    service.alert_source_last_run = defaultdict(lambda: datetime.min)
    service.policies = {
        "IMMEDIATELY": RecordingPolicy(),
        "HOURLY": RecordingPolicy(lambda d: (d.date(), d.hour)),
        "DAILY": RecordingPolicy(lambda d: d.date()),
        "NEVER": RecordingPolicy(lambda d: None),
    }

    return AlertRuntime(service, facts_holder)


def make_source(
    name,
    *,
    applies_to=None,
    require_stable_peer=False,
    post_failover_blackout=False,
    produces=(),
):
    """An `AlertSource` subclass that counts its `check()` calls.

    `produces` is a sequence of `(klass, args)`. A fresh `Alert` is built for each of them on
    every tick because `__handle_alert` stamps uuid, timestamps and dismissed state onto the
    object it is handed, so handing back the same one would carry the previous tick's answer.
    """

    async def check(self):
        self.checks += 1
        return [Alert(klass, args) for klass, args in produces]

    return type(
        f"{name}AlertSource",
        (AlertSource,),
        {
            "applies_to": applies_to,
            "require_stable_peer": require_stable_peer,
            "post_failover_blackout": post_failover_blackout,
            "checks": 0,
            "check": check,
        },
    )


def install_sources(monkeypatch, runtime, *source_classes):
    """Register instances of `source_classes` for the duration of one test.

    `ALERT_SOURCES` is a module-level dict that `AlertService.load()` fills at setup and that is
    empty under pytest, so `setitem` is enough and reverts itself.
    """
    sources = []
    for source_class in source_classes:
        source = source_class(runtime.service.middleware)
        monkeypatch.setitem(ALERT_SOURCES, source.name, source)
        sources.append(source)

    return sources


def seed_alert(klass, args, *, source, uuid):
    """An alert as `initialize()` would have restored it from the datastore."""
    return Alert(klass, args, node="A", _source=source, _uuid=uuid)
