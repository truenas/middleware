import datetime
from dataclasses import dataclass
from typing import Any

from middlewared.alert.base import (
    AlertClass,
    AlertCategory,
    AlertClassConfig,
    AlertLevel,
    Alert,
    NonDataclassAlertClass,
    ThreadedAlertSource,
)


class ScrubPausedAlert(NonDataclassAlertClass[str], AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.STORAGE,
        level=AlertLevel.WARNING,
        title="Scrub Is Paused",
        text="Scrub for pool %r is paused for more than 8 hours.",
    )


@dataclass(kw_only=True)
class ZpoolCapacityNoticeAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.STORAGE,
        level=AlertLevel.NOTICE,
        title="Pool Space Usage Is Above 85%",
        text="Space usage for pool '%(volume)s' is %(capacity)d%%.",
        proactive_support=True,
    )

    volume: str
    capacity: int

    @classmethod
    def key_from_args(cls, args: Any) -> Any:
        return [args['volume']]


@dataclass(kw_only=True)
class ZpoolCapacityWarningAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.STORAGE,
        level=AlertLevel.WARNING,
        title="Pool Space Usage Is Above 90%",
        text="Space usage for pool '%(volume)s' is %(capacity)d%%.",
        proactive_support=True,
    )

    volume: str
    capacity: int

    @classmethod
    def key_from_args(cls, args: Any) -> Any:
        return [args['volume']]


@dataclass(kw_only=True)
class ZpoolCapacityCriticalAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.STORAGE,
        level=AlertLevel.CRITICAL,
        title="Pool Space Usage Is Above 95%",
        text="Space usage for pool '%(volume)s' is %(capacity)d%%.",
        proactive_support=True,
    )

    volume: str
    capacity: int

    @classmethod
    def key_from_args(cls, args: Any) -> Any:
        return [args['volume']]


@dataclass(kw_only=True)
class ZpoolStatusAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.STORAGE,
        level=AlertLevel.CRITICAL,
        title="Pool Status Is Not Healthy",
        text="Pool %(volume)s state is %(state)s: %(status)s%(devices)s",
        proactive_support=True,
    )

    volume: str
    state: str
    status: str
    devices: str


@dataclass(kw_only=True)
class BootPoolStatusAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SYSTEM,
        level=AlertLevel.CRITICAL,
        title="Boot Pool Is Not Healthy",
        text="Boot pool status is %(status)s: %(status_detail)s.",
        proactive_support=True,
    )

    status: str
    status_detail: str


class ZpoolUpgradedAlert(NonDataclassAlertClass[str], AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.STORAGE,
        level=AlertLevel.NOTICE,
        title="New Feature Flags Are Available for Pool",
        text=(
            "New ZFS version or feature flags are available for pool '%s'. Upgrading pools is a one-time process that"
            " can prevent rolling the system back to an earlier TrueNAS version. It is recommended to read the TrueNAS"
            " release notes and confirm you need the new ZFS feature flags before upgrading a pool."
        ),
    )


class ZpoolsAlertSource(ThreadedAlertSource):
    """Consolidated alert source for all zpool-related periodic checks.

    This replaces several separate alert sources (VolumeStatusAlertSource,
    ZpoolCapacityAlertSource, ScrubPausedAlertSource, and the event-driven
    PoolUpgraded oneshot alert) with a single threaded source that queries
    zpool state once and evaluates all alert conditions together.

    The source is split into two sections:

    1. **Boot pool** — Always checked on every node (MASTER, BACKUP, and
       SINGLE). On HA systems both controllers have the boot pool imported
       at all times, so health, capacity, and scrub alerts for the boot
       pool must be evaluated regardless of failover state. This section
       runs unconditionally before any failover guard checks.

    2. **Data pools** — Only checked on the MASTER (or SINGLE) controller
       when no failover event is in progress. On HA BACKUP nodes, data
       pools are not imported so there is nothing to check. During an
       active failover event, data pool state is transitional and
       unreliable, so we return early with only the boot pool alerts to
       avoid false positives. Data pool alerts from the previous cycle
       will naturally be replaced once the failover completes and the
       next check cycle runs on the new MASTER.
    """

    def flatten_topology(self, topology):
        """Walk a pool topology tree and return all leaf disk vdevs.

        Iteratively traverses all vdev categories (data, stripe, cache,
        dedup, log, special, spares) and collects every leaf vdev whose
        ``vdev_type`` is ``"disk"``. Non-disk leaves (e.g. files) are
        skipped. The traversal is iterative (stack-based) to avoid
        recursion depth issues on deeply nested topologies.

        Args:
            topology: A pool topology dict as returned by
                ``zpool.query_impl`` with ``topology=True``. May be
                ``None`` if topology was not requested.

        Returns:
            A list of disk vdev dicts, each containing at minimum
            ``name``, ``guid``, ``state``, and ``children`` keys.
        """
        disks = []
        if not topology:
            return disks

        stack = []
        for key in ("data", "stripe", "cache", "dedup", "log", "special", "spares"):
            if topology[key] is not None:
                stack.extend(topology[key])

        while stack:
            vdev = stack.pop()
            if vdev["vdev_type"] == "disk":
                disks.append(vdev)
            stack.extend(vdev["children"])
        return disks

    def handle_unhealthy(self, pool, disks_in_db):
        """Check for non-ONLINE disks in the pool topology and build
        a detailed alert listing each bad disk.

        For every disk vdev that is not in the ONLINE state, we attempt
        to resolve its ZFS guid to a physical disk entry in the database
        (including expired/removed disks) to provide the user with a
        human-readable disk name, model, and serial number. If the disk
        is not found in the database, we fall back to the vdev name and
        ZFS guid.

        Args:
            pool: A single pool dict from ``zpool.query_impl`` with
                ``topology=True``.
            disks_in_db: Pre-fetched list from ``disk.query`` with
                ``include_expired=True``. Passed in from ``check_sync``
                so we query the database once for all pools rather than
                once per pool.

        Returns:
            A list containing zero or one ``ZpoolStatusAlert`` alerts.
            The alert text includes an HTML list of all bad disks when
            any are found.
        """
        alerts: list[Alert[Any]] = []
        bad_disks = []
        for disk_in_zpool in self.flatten_topology(pool["topology"]):
            if disk_in_zpool["state"] != "ONLINE":
                guid = disk_in_zpool["guid"]
                name = disk_in_zpool["name"]
                model = serial = ""
                if disk := self.middleware.call_sync(
                    "disk.disk_by_zfs_guid", disk_in_zpool["guid"], disks_in_db
                ):
                    name = disk["name"]
                    if disk["model"]:
                        model = disk["model"]
                    if disk["serial"]:
                        serial = disk["serial"]

                entry = f"Disk {name} in zpool guid {guid}"
                if model:
                    entry += f" with model {model}"
                if serial:
                    entry += f" with serial {serial}"

                bad_disks.append(entry)

        if bad_disks:
            alerts.append(
                Alert(
                    ZpoolStatusAlert(
                        volume=pool["name"],
                        state=pool["status"],
                        status=pool["status_detail"],
                        devices=(
                            f"<br>The following devices are not healthy:"
                            f"<ul><li>{'</li><li>'.join(bad_disks)}</li></ul>"
                        ),
                    ),
                )
            )
        return alerts

    def handle_upgraded(self, pool):
        """Check whether the pool has ZFS feature flags available for upgrade.

        A pool with ``status_code == "FEAT_DISABLED"`` has features that
        are supported by the running ZFS version but not yet enabled on
        the pool. This is common after a TrueNAS upgrade that ships a
        newer ZFS version.

        This replaced the previous event-driven oneshot ``PoolUpgraded``
        alert which suffered from a race condition: the ZFS pool import
        event fired before the pool's database entry was created, so the
        alert handler could never look up the pool and silently skipped
        alert creation.

        Args:
            pool: A single pool dict from ``zpool.query_impl``.

        Returns:
            A list containing zero or one ``ZpoolUpgradedAlert`` alerts.
        """
        alerts: list[Alert[Any]] = []
        if pool["status_code"] == "FEAT_DISABLED":
            alerts.append(Alert(ZpoolUpgradedAlert(pool["name"])))
        return alerts

    def handle_scrub(self, pool):
        """Check whether a scrub has been paused for an unreasonable duration.

        ZFS allows pausing an in-progress scrub. If a scrub remains
        paused for more than 8 hours, we alert the user since this
        likely indicates a forgotten pause rather than intentional
        behavior. Only active scrubs (not resilvers) are considered.

        Args:
            pool: A single pool dict from ``zpool.query_impl`` with
                ``scan=True``.

        Returns:
            A list containing zero or one ``ScrubPausedAlert`` alerts.
        """
        alerts: list[Alert[Any]] = []
        scan = pool["scan"]
        if not scan or scan["function"] != "SCRUB" or not scan["pause"]:
            return alerts

        threshold = datetime.datetime.now() - datetime.timedelta(hours=8)
        if scan["pause"] < threshold:
            alerts.append(Alert(ScrubPausedAlert(pool["name"])))
        return alerts

    def handle_boot_pool(self):
        """Check the boot pool for health, capacity, and scrub status.

        The boot pool is always imported on every controller in both
        SINGLE and HA configurations. On HA systems, both MASTER and
        BACKUP nodes have the boot pool available, so this method runs
        unconditionally — it is NOT gated behind any failover status
        check. This ensures boot pool problems are always visible
        regardless of which controller the user is viewing.

        Boot pool checks include:
          - Health status (``BootPoolStatusAlert`` if unhealthy)
          - Capacity thresholds (85%/90%/95% via ``handle_capacity``)
          - Scrub pause detection (via ``handle_scrub``)

        Note: The boot pool is intentionally excluded from the
        ``ZpoolUpgradedAlert`` check because the boot pool has
        certain ZFS features disabled by design and should never be
        manually upgraded by the user.

        Returns:
            A list of alerts for the boot pool (may be empty if the
            boot pool is healthy, under capacity thresholds, and has
            no paused scrub).
        """
        alerts: list[Alert[Any]] = []
        boot_pool = self.middleware.call_sync("boot.pool_name")
        for pool in self.middleware.call_sync(
            "zpool.query_impl",
            {"pool_names": [boot_pool], "properties": ["capacity"], "scan": True},
        ):
            if not pool["healthy"]:
                alerts.append(
                    Alert(
                        BootPoolStatusAlert(
                            status=pool["status"],
                            status_detail=pool["status_detail"],
                        ),
                    )
                )
            alerts.extend(self.handle_capacity(pool))
            alerts.extend(self.handle_scrub(pool))
        return alerts

    def handle_capacity(self, pool):
        """Check pool space usage against tiered alert thresholds.

        Evaluates capacity against three thresholds in descending order:
          - >= 95%: CRITICAL
          - >= 90%: WARNING
          - >= 85%: NOTICE

        The first matching threshold wins (highest severity takes
        priority).

        **Anti-oscillation logic:** At boundary values one percent below
        each threshold (94%, 89%, 84%), the method preserves whatever
        alert level was emitted on the previous cycle instead of
        re-evaluating. This prevents alert flapping when pool capacity
        fluctuates around a threshold — e.g. a pool bouncing between
        84% and 85% would otherwise alternate between NOTICE and no
        alert every check cycle.

        Previous state is stored in the middleware volatile cache
        (``cache.put``/``cache.get``) keyed by pool name. The cache is
        lost on reboot, which is acceptable — after reboot there is no
        previous alert to preserve, and the next threshold crossing will
        establish fresh state.

        Args:
            pool: A single pool dict from ``zpool.query_impl`` with
                ``properties=["capacity"]``.

        Returns:
            A list containing zero or one capacity alert.
        """
        alerts: list[Alert[Any]] = []
        capacity = pool["properties"]["capacity"]["value"]
        pool_name = pool["name"]
        cache_key = f"ZpoolCapacityAlert:{pool_name}"

        for target_capacity, alert_class in [
            (95, ZpoolCapacityCriticalAlert),
            (90, ZpoolCapacityWarningAlert),
            (85, ZpoolCapacityNoticeAlert),
        ]:
            if capacity >= target_capacity:
                alerts.append(
                    Alert(alert_class(volume=pool_name, capacity=capacity))
                )
                self.middleware.call_sync("cache.put", cache_key, target_capacity)
                break
            elif capacity == target_capacity - 1:
                # Boundary value: preserve the previous alert level to
                # prevent oscillation when capacity fluctuates around
                # a threshold (e.g. 84% ↔ 85%).
                try:
                    prev_threshold = self.middleware.call_sync("cache.get", cache_key)
                    prev_class = dict([
                        (95, ZpoolCapacityCriticalAlert),
                        (90, ZpoolCapacityWarningAlert),
                        (85, ZpoolCapacityNoticeAlert),
                    ])[prev_threshold]
                    alerts.append(
                        Alert(prev_class(volume=pool_name, capacity=capacity))
                    )
                except KeyError:
                    pass
                break
        else:
            # Below all thresholds — clear cached state
            self.middleware.call_sync("cache.pop", cache_key)

        return alerts

    def check_sync(self):
        """Main entry point called by the alert system on each check cycle.

        Execution is split into two phases:

        1. **Boot pool checks** (unconditional) — The boot pool is
           imported on every node at all times (MASTER, BACKUP, and
           SINGLE). Health, capacity, and scrub alerts for the boot
           pool are always evaluated first, before any failover guard.

        2. **Data pool checks** (guarded) — On HA enterprise systems,
           data pools are only imported on the MASTER controller. We
           skip data pool checks entirely when:
             - A failover event is currently in progress (pool state
               is transitional and unreliable)
             - This node is not the MASTER (data pools are not imported
               on the BACKUP node)

           In either case we return early with only the boot pool
           alerts. This is safe because the BACKUP node never has data
           pools imported, so there are no data pool alerts to preserve.

        Data pool checks use a single ``zpool.query_impl`` call with
        ``topology=True``, ``scan=True``, and ``properties=["capacity"]``
        to fetch all needed information in one shot. The disk database
        is also queried once and passed to ``handle_unhealthy`` for all
        pools to avoid redundant queries.

        Returns:
            A list of all active alerts across boot pool and data pools.
        """
        alerts: list[Alert[Any]] = []
        # Always check the boot pool on every node — both MASTER and
        # BACKUP have it imported at all times.
        alerts.extend(self.handle_boot_pool())

        # Data pools are only imported on the MASTER controller.
        # Skip if a failover event is in progress or we are not MASTER.
        if self.middleware.call_sync("system.is_enterprise"):
            if self.middleware.call_sync("failover.in_progress"):
                return alerts
            elif self.middleware.call_sync("failover.status") != "MASTER":
                return alerts

        zpools_in_db = [
            i["vol_name"]
            for i in self.middleware.call_sync("datastore.query", "storage.volume")
        ]
        if not zpools_in_db:
            return alerts

        disks_in_db = self.middleware.call_sync(
            "disk.query", [], {"extra": {"include_expired": True}}
        )
        for pool in self.middleware.call_sync(
            "zpool.query_impl",
            {
                "pool_names": zpools_in_db,
                "topology": True,
                "scan": True,
                "properties": ["capacity"],
            },
        ):
            alerts.extend(self.handle_upgraded(pool))
            alerts.extend(self.handle_unhealthy(pool, disks_in_db))
            alerts.extend(self.handle_scrub(pool))
        return alerts
