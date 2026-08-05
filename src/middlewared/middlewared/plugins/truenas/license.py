import contextlib
import os
from typing import Any

from middlewared.api import api_method
from middlewared.api.current import (
    TrueNASLicenseUploadOptions,
    TrueNASLicenseUploadArgs,
    TrueNASLicenseUploadResult,
    TrueNASLicenseFingerprintArgs,
    TrueNASLicenseFingerprintResult,
    TrueNASLicenseInfoArgs,
    TrueNASLicenseInfoResult,
)
from middlewared.service import Service, ValidationError, private
from middlewared.plugins.truenas.tn import EULA_PENDING_PATH
from middlewared.utils.license import (
    LEGACY_LICENSE_FILE,
    LicenseInfo,
    get_fingerprint_b64,
    get_legacy_license_info,
    get_license,
    upload_license,
)
from truenas_pylicensed import LicenseType


def _license_info_json(info: LicenseInfo) -> dict[str, Any]:
    """
    Project a LicenseInfo onto the public `truenas.license.info` payload.
    """
    return {
        "id": info.id,
        "type": info.type.name,
        "model": info.model,
        "expires_at": info.license_expires_at or info.support_expires_at,
        "features": [
            {
                "name": feature.name,
                "start_date": feature.start_date,
                "expires_at": feature.expires_at,
                "source": feature.source,
                "type": feature.type,
            }
            for feature in info.features.values()
        ],
        "serials": list(info.serials),
        "enclosures": dict(info.enclosures),
        "contract_type": info.contract_type,
    }


class TrueNASLicenseService(Service):
    class Config:
        namespace = "truenas.license"
        cli_private = True

    @api_method(
        TrueNASLicenseUploadArgs,
        TrueNASLicenseUploadResult,
        audit="License upload",
        roles=["FULL_ADMIN"],
        check_annotations=True,
    )
    def upload(self, license_: str, options: TrueNASLicenseUploadOptions) -> None:
        """Upload a PEM-wrapped license file."""
        had_license = self.info_private() is not None

        with upload_license(str(license_)) as lic:
            if not lic.valid:
                raise ValidationError("license", f"Invalid license: {lic.error}")

            if lic.type == LicenseType.ENTERPRISE_HA:
                if not self.middleware.call_sync("system.is_ha_capable"):
                    raise ValidationError("license", "This is not an HA capable system")

        with contextlib.suppress(FileNotFoundError):
            os.remove(LEGACY_LICENSE_FILE)

        get_legacy_license_info.cache_clear()

        self.middleware.call_sync("etc.generate", "rc")

        self.middleware.call_sync("alert.alert_source_clear_run", "LicenseStatus")

        if options.ha_propagate:
            if lic.type in (
                LicenseType.ENTERPRISE_HA,
                LicenseType.ENTERPRISE_SINGLE
            ):
                if lic.type == LicenseType.ENTERPRISE_HA:
                    self._configure_ha_license()

                with open(EULA_PENDING_PATH, "a+") as f:
                    os.fchmod(f.fileno(), 0o600)

        self.middleware.run_coroutine(
            self.middleware.call_hook('system.post_license_update', had_license=had_license), wait=False,
        )

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

    @private
    def reset_legacy_license_cache(self) -> None:
        get_legacy_license_info.cache_clear()

    @api_method(
        TrueNASLicenseInfoArgs,
        TrueNASLicenseInfoResult,
        roles=["READONLY_ADMIN"],
        check_annotations=True,
    )
    def info(self) -> dict[str, Any] | None:
        """Returns the parsed license object, or null if no license exists."""
        info = self.info_private()
        return _license_info_json(info) if info is not None else None

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
