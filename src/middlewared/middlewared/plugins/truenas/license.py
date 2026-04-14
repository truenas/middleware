import contextlib
from dataclasses import asdict
import os
from typing import Any

from middlewared.api import api_method
from middlewared.api.current import (
    TrueNASLicenseUploadOptions,
    TrueNASLicenseUploadArgs,
    TrueNASLicenseUploadResult,
    TrueNASLicenseInfoArgs,
    TrueNASLicenseInfoResult,
)
from middlewared.service import Service, ValidationError, private
from middlewared.plugins.truenas.tn import EULA_PENDING_PATH
from truenas_pylicensed import LicenseType

from .license_legacy_utils import LEGACY_LICENSE_FILE, get_legacy_license_info
from .license_utils import (
    LicenseInfo,
    configure_ha_license,
    get_license_info,
    upload_license,
)


class TrueNASLicenseService(Service):
    class Config:
        namespace = "truenas.license"
        cli_private = True

    @api_method(
        TrueNASLicenseUploadArgs,
        TrueNASLicenseUploadResult,
        roles=["FULL_ADMIN"],
        check_annotations=True,
    )
    def upload(self, license_: str, options: TrueNASLicenseUploadOptions) -> None:
        """Upload a PEM-wrapped license file."""
        had_license = self.info_private() is not None

        with upload_license(license_) as lic:
            if not lic.valid:
                raise ValidationError("license", f"Invalid license: {lic.error}")

            if lic.type == LicenseType.ENTERPRISE_HA:
                if not self.middleware.call_sync("system.is_ha_capable"):
                    raise ValidationError("license", "This is not an HA capable system")

        with contextlib.suppress(FileNotFoundError):
            os.remove(LEGACY_LICENSE_FILE)

        self.middleware.call_sync("etc.generate", "rc")

        self.call_sync2(self.s.alert.alert_source_clear_run, "LicenseStatus")

        if options.ha_propagate:
            if lic.type in (
                LicenseType.ENTERPRISE_HA,
                LicenseType.ENTERPRISE_SINGLE
            ):
                if lic.type == LicenseType.ENTERPRISE_HA:
                    configure_ha_license(self.middleware, had_license)

                with open(EULA_PENDING_PATH, "a+") as f:
                    os.fchmod(f.fileno(), 0o600)

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
        result: dict[str, Any] | None = None
        info = self.info_private()
        if info is not None:
            result = asdict(info)
            result["type"] = info.type.name

        return result

    @private
    def info_private(self) -> LicenseInfo | None:
        return get_license_info() or get_legacy_license_info()
