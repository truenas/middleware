from collections.abc import Iterable
import contextlib
import os
from typing import TYPE_CHECKING, Any

from pydantic import Secret
from truenas_pylicensed import LicenseStatus, LicenseType, verify
from truenas_pylicensed.features import LicenseFeature

from middlewared.alert.source.license_usage import UnlicensedFeaturesInUseAlert
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
from middlewared.common.license import LicenseDelegate
from middlewared.plugins.truenas.tn import EULA_PENDING_PATH
from middlewared.service import Service, ValidationError, job, private
from middlewared.service_exception import CallError
from middlewared.utils.entitlements import (
    FEATURE_DISPLAY_NAMES,
    POLICY,
    DerivedEntitlement,
    EntitlementFacts,
    check_entitlement,
)
from middlewared.utils.hardware import get_hardware_class
from middlewared.utils.license import (
    HW_LICENSE_ERROR_FILE,
    LEGACY_LICENSE_FILE,
    LicenseInfo,
    LicenseOrigin,
    get_fingerprint_b64,
    get_legacy_license_info,
    get_license,
    upload_license,
)

if TYPE_CHECKING:
    from middlewared.job import Job
    from middlewared.main import Middleware


# Features whose revoke has no runtime action: their gates read the entitlement live and the
# usage alert reports what is still in use.
ALERT_ONLY: frozenset[str] = frozenset(
    {
        LicenseFeature.DEDUP,
        LicenseFeature.MISSION_CRITICAL,
        LicenseFeature.NETWORK_FEC,
        LicenseFeature.NVMEOF_SPDK,
        LicenseFeature.STIG,
        DerivedEntitlement.PROACTIVE_SUPPORT,
    }
)


def snapshot(status: LicenseStatus | None = None) -> dict[str, bool]:
    status = verify() if status is None else status
    facts = EntitlementFacts(hardware_class=get_hardware_class(), license=get_license(status))
    return {key: check_entitlement(key, facts).entitled for key in POLICY}


def diff(previous: dict[str, bool], current: dict[str, bool]) -> dict[str, bool]:
    return {key: current[key] for key in POLICY if previous[key] != current[key]}


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
        check_annotations=True,
    )
    def upload(self, license_: Secret[LongNonEmptyString], options: TrueNASLicenseUploadOptions) -> None:
        """Upload a PEM-wrapped license file."""
        current = self.info_private()
        had_license = current is not None and current.origin is LicenseOrigin.ISSUED
        previous = snapshot()

        # `check_annotations` hands the method the undumped model value, so the PEM arrives still
        # boxed in the Secret that keeps it off the audit trail.
        with upload_license(license_.get_secret_value()) as lic:
            if not lic.valid:
                raise ValidationError("license", f"Invalid license: {lic.error}")

            if lic.has_feature(LicenseFeature.HA):
                if not self.middleware.call_sync("system.is_ha_capable"):
                    raise ValidationError("license", "This is not an HA capable system")
            else:
                self._refuse_ha_loss()

            updated = snapshot(lic)

        with contextlib.suppress(FileNotFoundError):
            os.remove(LEGACY_LICENSE_FILE)

        get_legacy_license_info.cache_clear()

        if changes := diff(previous, updated):
            self.middleware.call_sync("truenas.license.apply", changes)

        self.call_sync2(self.s.alert.alert_source_clear_run, "LicenseStatus")

        if options.ha_propagate:
            if lic.type == LicenseType.ENTERPRISE:
                if lic.has_feature(LicenseFeature.HA):
                    self._configure_ha_license()

                with open(EULA_PENDING_PATH, "a+") as f:
                    os.fchmod(f.fileno(), 0o600)

        # Only the unlicensed -> licensed transition sets the profile; removing a license
        # deliberately does not move it back down.
        if not had_license and updated[LicenseFeature.MISSION_CRITICAL]:
            self.call_sync2(self.s.update.set_profile, "MISSION_CRITICAL")

    def _configure_ha_license(self) -> None:
        try:
            self.middleware.call_sync("failover.ensure_remote_client")
        except Exception as e:
            # this is fatal because we can't determine what the remote ip address
            # is to so any failover.call_remote calls will fail
            raise ValidationError("license", f"Failed to determine remote heartbeat IP address: {e}")

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

    def _delegates_for(self, keys: Iterable[str]) -> list[LicenseDelegate]:
        keys = set(keys)
        delegates: list[LicenseDelegate] = []
        # HA goes first: other delegates read the peer through the remote client its grant creates.
        for key in sorted(POLICY, key=lambda key: key != LicenseFeature.HA):
            if key in keys and (delegate := self.delegates.get(key)) is not None and delegate not in delegates:
                delegates.append(delegate)
        return delegates

    @private
    @job(lock="license_apply", lock_queue_size=None)
    async def apply(self, job: "Job", changes: dict[str, bool]) -> None:
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
                self.logger.error("%s: license apply failed: %s", delegate.name, e.errmsg)
                failed[delegate.name] = e.errmsg
            except Exception as e:
                self.logger.error("%s: license apply failed", delegate.name, exc_info=True)
                failed[delegate.name] = str(e)

        if await self.middleware.call("failover.is_single_master_node"):
            await self.refresh_usage_alert()

        if failed:
            raise CallError("License applied; steps failed: " + "; ".join(f"{k}: {v}" for k, v in failed.items()))

    @private
    async def revoke_pending(self) -> dict[tuple[str, ...], str]:
        live = await self.middleware.run_in_thread(snapshot)
        lines: dict[tuple[str, ...], str] = {}
        for delegate in self._delegates_for(key for key in self.delegates if not live[key]):
            if any(live[feature] for feature in delegate.features):
                continue

            names = ", ".join(FEATURE_DISPLAY_NAMES[feature] for feature in delegate.features)
            if pending := await delegate.revoke_pending():
                lines[delegate.features] = f"{names}: {pending}"
        return lines

    @private
    async def refresh_usage_alert(self) -> None:
        revokes = await self.revoke_pending()
        revoking = {feature for features in revokes for feature in features}
        usage = await self.call2(self.s.truenas.entitlements.usage)
        lines = [
            f"{FEATURE_DISPLAY_NAMES[key]}: {entry['message']}"
            for key, entry in usage.items()
            # HA's "use" is the hardware itself, which nobody can remove.
            if key != LicenseFeature.HA and key not in revoking and not entry["entitled"] and entry["in_use"]
        ] + list(revokes.values())
        if lines:
            await self.call2(self.s.alert.oneshot_create, UnlicensedFeaturesInUseAlert("\n".join(lines)))
        else:
            await self.call2(self.s.alert.oneshot_delete, "UnlicensedFeaturesInUse", None)

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
