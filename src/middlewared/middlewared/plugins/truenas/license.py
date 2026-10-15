from collections.abc import Callable, Iterable
import contextlib
from datetime import datetime
import enum
import errno
import json
import os
import threading
import time
from typing import TYPE_CHECKING, Any, TypedDict
import uuid

from pydantic import Secret
from truenas_os_pyutils.io import atomic_write
from truenas_pylicensed import LicenseError, LicenseStatus, LicenseType, verify
from truenas_pylicensed.features import LicenseFeature

from middlewared.api import api_method
from middlewared.api.base import LongNonEmptyString
from middlewared.api.current import (
    LicenseFeatureEntry,
    LicenseInfoEntry,
    TrueNASLicenseFingerprintArgs,
    TrueNASLicenseFingerprintResult,
    TrueNASLicenseInfoArgs,
    TrueNASLicenseInfoResult,
    TrueNASLicenseUploadArgs,
    TrueNASLicenseUploadOptions,
    TrueNASLicenseUploadResult,
)
from middlewared.auth import TruenasNodeSessionManagerCredentials
from middlewared.common.license import LicenseDelegate
from middlewared.plugins.truenas.tn import EULA_PENDING_PATH
from middlewared.service import Service, ValidationError, job, periodic, private
from middlewared.service_exception import CallError
from middlewared.utils import MIDDLEWARE_RUN_DIR
from middlewared.utils.entitlements import FEATURE_DISPLAY_NAMES, POLICY, EntitlementFacts, check_entitlement
from middlewared.utils.hardware import get_hardware_class
from middlewared.utils.license import (
    DAEMON_ERRORS,
    HW_LICENSE_ERROR_FILE,
    LEGACY_LICENSE_FILE,
    LICENSE_FILE,
    LicenseInfo,
    LicenseOrigin,
    get_fingerprint_b64,
    get_legacy_license_info,
    get_license,
    is_freenas_model,
    parse_legacy_license,
    upload_license,
)

if TYPE_CHECKING:
    from middlewared.api.base.server.app import App
    from middlewared.job import Job
    from middlewared.main import Middleware


JOURNAL_FILE = f"{MIDDLEWARE_RUN_DIR}/license_apply_pending.json"

# Features whose revoke has no runtime action: their gates read the entitlement live and the
# usage alert reports what is still in use.
ALERT_ONLY: frozenset[str] = frozenset(
    {
        LicenseFeature.DEDUP,
        LicenseFeature.MISSION_CRITICAL,
        LicenseFeature.NETWORK_FEC,
        LicenseFeature.NVMEOF_SPDK,
        LicenseFeature.STIG,
    }
)

# Held from the snapshot before a licence change through the enqueue of its apply, so apply jobs
# queue in install order. Thread pool only: the holder waits on the event loop to enqueue.
_upload_lock = threading.Lock()
_journal_lock = threading.Lock()


class _Live(enum.Enum):
    LIVE = enum.auto()


class _JournalEntry(TypedDict):
    id: str
    changes: dict[str, bool]


def snapshot(
    status: LicenseStatus | None = None, *, license: LicenseInfo | None | _Live = _Live.LIVE
) -> dict[str, bool]:
    """Entitlement of every policy key. Refuses rather than reading a daemon error as unlicensed."""
    if license is _Live.LIVE:
        status = verify() if status is None else status
        if status.code in DAEMON_ERRORS:
            raise CallError("license daemon unavailable", errno.EAGAIN)
        license = get_license(status)
    facts = EntitlementFacts(hardware_class=get_hardware_class(), license=license)
    return {key: check_entitlement(key, facts).entitled for key in POLICY}


def diff(previous: dict[str, bool], current: dict[str, bool]) -> dict[str, bool]:
    return {key: current[key] for key in POLICY if previous[key] != current[key]}


def _journal_read() -> list[_JournalEntry]:
    try:
        with open(JOURNAL_FILE) as f:
            entries: list[_JournalEntry] = json.load(f)
    except FileNotFoundError:
        return []
    return entries


def _journal_write(entries: list[_JournalEntry]) -> None:
    with atomic_write(JOURNAL_FILE, "w", perms=0o600) as f:
        json.dump(entries, f)


def journal_append(changes: dict[str, bool]) -> str:
    entry_id = str(uuid.uuid4())
    with _journal_lock:
        _journal_write(_journal_read() + [{"id": entry_id, "changes": changes}])
    return entry_id


def journal_remove(entry_id: str) -> None:
    with _journal_lock:
        _journal_write([entry for entry in _journal_read() if entry["id"] != entry_id])


def _license_entry(info: LicenseInfo) -> LicenseInfoEntry:
    """
    Project a LicenseInfo onto the public `truenas.license.info` payload.

    There is no license-wide expiry to project. Expiry belongs to individual features,
    so `features[].expires_at` is the only date here, and the end of the support
    contract is the SUPPORT entry's.
    """
    # Copied rather than passed through: pydantic's strict mode rejects a tuple for a list and a
    # MappingProxyType for a dict, and LicenseType is an IntEnum that would otherwise go out as a
    # bare integer.
    return LicenseInfoEntry(
        id=info.id,
        type=info.type.name,
        model=info.model,
        features=[
            LicenseFeatureEntry(
                name=feature.name,
                start_date=feature.start_date,
                expires_at=feature.expires_at,
                type=feature.type,
            )
            for feature in info.features.values()
        ],
        serials=list(info.serials),
        enclosures=dict(info.enclosures),
        contract_type=info.contract_type,
        issued_at=info.issued_at,
    )


class TrueNASLicenseService(Service):
    class Config:
        namespace = "truenas.license"
        cli_private = True

    def __init__(self, middleware: "Middleware") -> None:
        super().__init__(middleware)
        self.delegates: dict[str, LicenseDelegate] = {}

    @api_method(
        TrueNASLicenseUploadArgs,
        TrueNASLicenseUploadResult,
        audit="License upload",
        roles=["FULL_ADMIN"],
        pass_app=True,
        check_annotations=True,
    )
    def upload(self, app: "App", license_: Secret[LongNonEmptyString], options: TrueNASLicenseUploadOptions) -> None:
        """Upload a PEM-wrapped license file."""
        # The HA peer and TNC (an internal call) install licenses without a user deciding to.
        interactive = app is not None and not isinstance(
            app.authenticated_credentials, TruenasNodeSessionManagerCredentials
        )
        if interactive:
            if self.middleware.call_sync("failover.status") == "BACKUP":
                raise CallError("A license cannot be uploaded on the standby controller", errno.EBUSY)
            if self.middleware.call_sync("failover.in_progress"):
                raise CallError("A license cannot be uploaded while a failover event is in progress", errno.EBUSY)

        had_license = False
        lic: LicenseStatus | None = None

        def mutate() -> dict[str, bool]:
            nonlocal had_license, lic
            installed = verify()
            if installed.code in DAEMON_ERRORS:
                raise CallError("license daemon unavailable", errno.EAGAIN)
            installed_info = get_license(installed)
            had_license = installed_info is not None and installed_info.origin is LicenseOrigin.ISSUED
            # `check_annotations` hands the method the undumped model value, so the PEM arrives still
            # boxed in the Secret that keeps it off the audit trail.
            with upload_license(license_.get_secret_value()) as lic:
                if lic.code in DAEMON_ERRORS:
                    raise CallError("license daemon unavailable", errno.EAGAIN)

                if not lic.valid:
                    raise ValidationError("license", f"Invalid license: {lic.error}")

                if lic.has_feature(LicenseFeature.HA):
                    if not self.middleware.call_sync("system.is_ha_capable"):
                        raise ValidationError("license", "This is not an HA capable system")
                else:
                    self._refuse_ha_loss()

                # A delivery must not undo a newer license, nor put a test license (which skips the serial
                # check) over a production one. The daemon does not read legacy licenses, so one never blocks.
                if not interactive and installed.valid and not installed.test:
                    if lic.test:
                        raise ValidationError("license", "A test license cannot replace the installed license")
                    assert lic.issued_at is not None and installed.issued_at is not None
                    if datetime.fromisoformat(lic.issued_at) < datetime.fromisoformat(installed.issued_at):
                        raise ValidationError("license", "The license is older than the installed license")

                current = snapshot(lic)

            with contextlib.suppress(FileNotFoundError):
                os.remove(LEGACY_LICENSE_FILE)

            get_legacy_license_info.cache_clear()
            return current

        current = self._change(mutate)
        assert lic is not None

        # Only the unlicensed -> licensed transition sets the profile; removing a license
        # deliberately does not move it back down.
        if not had_license and current[LicenseFeature.MISSION_CRITICAL]:
            self.call_sync2(self.s.update.set_profile, "MISSION_CRITICAL")

        if options.ha_propagate:
            if lic.type == LicenseType.ENTERPRISE:
                if lic.has_feature(LicenseFeature.HA):
                    self._configure_ha_license()

                with open(EULA_PENDING_PATH, "a+") as f:
                    os.fchmod(f.fileno(), 0o600)

        self.call_sync2(self.s.alert.alert_source_clear_run, "LicenseStatus")

    def _configure_ha_license(self) -> None:
        # The license is already installed here, so a propagation failure is logged, never raised.
        try:
            self.middleware.call_sync("failover.ensure_remote_client")
        except Exception:
            # Without the remote heartbeat IP address no failover.call_remote can reach the peer.
            self.logger.error("Failed to determine remote heartbeat IP address", exc_info=True)
            return

        try:
            self.middleware.call_sync("failover.call_remote", "failover.ensure_remote_client")
        except Exception:
            # this is not fatal, so no reason to return early
            # it just means that any "failover.call_remote" calls initiated from the remote node
            # will fail but that shouldn't be happening anyway
            self.logger.warning(
                "Remote node failed to determine this nodes heartbeat IP address",
                exc_info=True,
            )

        try:
            self.middleware.call_sync("failover.send_license")
        except Exception:
            self.logger.warning("Failed to send file to remote node", exc_info=True)

    def _refuse_ha_loss(self) -> None:
        if self.middleware.call_sync("interface.query", [["failover_virtual_aliases", "!=", []]]):
            raise ValidationError("license", "An HA license is required while failover virtual IPs are configured")

    def _change(self, mutate: Callable[[], dict[str, bool]]) -> dict[str, bool]:
        """`mutate` installs or removes the license and returns the resulting snapshot; it raises to abort."""
        with _upload_lock:
            previous = snapshot()
            current = mutate()
            if changes := diff(previous, current):
                self.middleware.call_sync("truenas.license.apply", changes, journal_append(changes))
        return current

    def _delegates_for(self, keys: Iterable[str]) -> list[LicenseDelegate]:
        keys = set(keys)
        if unhandled := sorted(keys - self.delegates.keys() - ALERT_ONLY):
            raise CallError(f"No license delegate for: {', '.join(unhandled)}")

        delegates: list[LicenseDelegate] = []
        # HA goes first: other delegates reach the peer through the remote client its grant creates.
        for key in sorted(POLICY, key=lambda key: key != LicenseFeature.HA):
            if key in keys and (delegate := self.delegates.get(key)) is not None and delegate not in delegates:
                delegates.append(delegate)
        return delegates

    @private
    @job(lock="license_apply", lock_queue_size=None)
    async def apply(self, job: "Job", changes: dict[str, bool], journal_id: str | None = None) -> dict[str, list[str]]:
        if unknown := set(changes) - set(POLICY):
            raise CallError(f"Unknown license features: {', '.join(sorted(unknown))}")

        # A key that no longer matches the installed license belongs to a superseded change.
        live = await self.middleware.run_in_thread(snapshot)
        skipped = sorted(key for key, value in changes.items() if live[key] != value)
        changes = {key: value for key, value in changes.items() if key not in skipped}

        await self.middleware.call("failover.status_refresh")
        await self.call2(self.s.alert.invalidate_applicability)

        failed: dict[str, str] = {}
        for delegate in self._delegates_for(changes):
            subset = {key: value for key, value in changes.items() if key in delegate.features}
            try:
                if delegate.active_only and not await delegate.is_active():
                    continue
                await delegate.apply(subset)
            except CallError as e:
                failed[delegate.name] = e.errmsg
            except Exception as e:
                self.logger.error("%s: license apply failed", delegate.name, exc_info=True)
                failed[delegate.name] = str(e)

        if journal_id is not None:
            await self.middleware.run_in_thread(journal_remove, journal_id)

        await self.call2(self.s.alert.alert_source_clear_run, "UnlicensedFeaturesInUse")

        if failed:
            raise CallError("License applied; steps failed: " + "; ".join(f"{k}: {v}" for k, v in failed.items()))

        return {"applied": sorted(changes), "skipped": skipped}

    @periodic(interval=86400, run_on_start=True)
    @private
    def replay_journal(self) -> None:
        # Under the lock so an entry appended by a change that has not enqueued its apply yet is not
        # enqueued twice.
        with _upload_lock:
            if not (entries := _journal_read()):
                return

            queued = {
                args[1]
                for queued_job in self.middleware.call_sync(
                    "core.get_jobs",
                    [["method", "=", "truenas.license.apply"], ["state", "in", ["WAITING", "RUNNING"]]],
                )
                if len(args := queued_job["arguments"]) > 1
            }
            for entry in entries:
                if entry["id"] not in queued:
                    self.middleware.call_sync("truenas.license.apply", entry["changes"], entry["id"])

    @private
    async def revoke_pending(self) -> list[str]:
        live = await self.middleware.run_in_thread(snapshot)
        lines: list[str] = []
        for delegate in self._delegates_for(key for key in self.delegates if not live[key]):
            if any(live[feature] for feature in delegate.features):
                continue

            names = ", ".join(FEATURE_DISPLAY_NAMES[feature] for feature in delegate.features)
            try:
                pending = await delegate.revoke_pending()
            except Exception:
                self.logger.debug("%s: failed to determine revoke state", delegate.name, exc_info=True)
                lines.append(f"{names}: revoke state could not be determined")
                continue

            if pending:
                recovery = json.dumps({feature: False for feature in delegate.features})
                lines.append(f"{names}: {pending}; retry with truenas.license.apply {recovery}")
        return lines

    @private
    def install_legacy(self, blob: str) -> None:
        try:
            parsed = parse_legacy_license(blob.strip("\n"))
        except Exception as e:
            raise ValidationError("license", f"Invalid legacy license: {e}")

        if is_freenas_model(parsed.model):
            raise ValidationError("license", "A FreeNAS license cannot be installed")

        if not parsed.has_feature(LicenseFeature.HA):
            self._refuse_ha_loss()

        def mutate() -> dict[str, bool]:
            installed = verify()
            if installed.code in DAEMON_ERRORS:
                raise CallError("license daemon unavailable", errno.EAGAIN)
            if installed.valid:
                raise ValidationError("license", "A legacy license cannot replace the installed license")

            v2_removed = False
            with contextlib.suppress(FileNotFoundError):
                os.unlink(LICENSE_FILE)
                v2_removed = True

            with atomic_write(LEGACY_LICENSE_FILE, "w", perms=0o600) as f:
                f.write(blob)

            get_legacy_license_info.cache_clear()

            if v2_removed:
                # Until the daemon drops the removed license it would still answer with it, and the
                # apply would read every key as superseded.
                for _ in range(6):
                    if verify().code == LicenseError.NO_LICENSE:
                        break
                    time.sleep(0.5)
                else:
                    raise CallError("License daemon did not drop the removed license", errno.ETIMEDOUT)

            return snapshot(license=get_legacy_license_info())

        self._change(mutate)

    @private
    def installed_pem(self) -> str | None:
        # Mid-upload the file holds a license that may still be rolled back.
        with _upload_lock:
            try:
                with open(LICENSE_FILE) as f:
                    return f.read()
            except FileNotFoundError:
                return None

    @private
    def reset_legacy_license_cache(self) -> None:
        get_legacy_license_info.cache_clear()

    @api_method(
        TrueNASLicenseInfoArgs,
        TrueNASLicenseInfoResult,
        roles=["READONLY_ADMIN"],
        check_annotations=True,
    )
    def info(self) -> LicenseInfoEntry | None:
        """Returns the parsed license object, or null if no license exists."""
        info = self.info_private()
        return _license_entry(info) if info is not None else None

    @api_method(
        TrueNASLicenseFingerprintArgs,
        TrueNASLicenseFingerprintResult,
        roles=["READONLY_ADMIN"],
        check_annotations=True,
    )
    def fingerprint(self) -> str:
        """Return the system hardware fingerprint as a base64-encoded JSON string."""
        return get_fingerprint_b64()

    @private
    def info_private(self) -> LicenseInfo | None:
        return get_license()

    @private
    def process_hw_license_error(self) -> None:
        if os.path.exists(HW_LICENSE_ERROR_FILE):
            try:
                with open(HW_LICENSE_ERROR_FILE) as f:
                    self.logger.error("truenas-hw-license.py: %s", f.read().strip())
            finally:
                os.unlink(HW_LICENSE_ERROR_FILE)


async def on_system_ready(middleware: "Middleware", event_type: str, args: Any) -> None:
    try:
        await middleware.call("truenas.license.process_hw_license_error")
    except Exception:
        middleware.logger.error("Error processing hardware entitlement error file", exc_info=True)


async def setup(middleware: "Middleware") -> None:
    # Every plugin module is imported before any setup runs, so every delegate class is registered.
    instances = {cls: cls(middleware) for cls in set(LicenseDelegate.by_feature.values())}
    middleware.services.truenas.license.delegates = {
        feature: instances[cls] for feature, cls in LicenseDelegate.by_feature.items()
    }
    middleware.event_subscribe("system.ready", on_system_ready)
