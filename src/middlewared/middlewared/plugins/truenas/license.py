import os

from middlewared.api import api_method
from middlewared.api.current import (
    TrueNASLicenseUploadArgs,
    TrueNASLicenseUploadResult,
    TrueNASLicenseInfoArgs,
    TrueNASLicenseInfoResult,
)
from middlewared.service import Service, ValidationError
from middlewared.plugins.truenas.tn import EULA_PENDING_PATH
from truenas_pylicensed import LicenseType

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
    )
    def upload(self, license_: str) -> None:
        """Upload a PEM-wrapped license file."""
        with upload_license(license_) as lic:
            if not lic.valid:
                raise ValidationError(
                    "truenas.license.upload", f"Invalid license: {lic.error}"
                )

            # FIXME: is this even needed still??
            self.middleware.call_sync("etc.generate", "rc")
            # FIXME: probably need new license but have to have
            # old for backwards compat??
            # TODO: what do we do if legacy license exists
            # and we get a new one? raise ValidationError
            # or maybe add a "replace_legacy" boolean to
            # new API so that the old one is removed (need
            # to update in-memory cache if we do this)
            self.call_sync2(self.s.alert.alert_source_clear_run, 'LicenseStatus')
            if lic.type in (
                LicenseType.ENTERPRISE_HA,
                LicenseType.ENTERPRISE_SINGLE
            ):
                if lic.type == LicenseType.ENTERPRISE_HA:
                    configure_ha_license(self)

                with open(EULA_PENDING_PATH, "a+") as f:
                    os.fchmod(f.fileno(), 0o600)


    @api_method(
        TrueNASLicenseInfoArgs,
        TrueNASLicenseInfoResult,
        roles=["READONLY_ADMIN"],
    )
    def info(self) -> LicenseInfo | None:
        """Returns the parsed license object, or null if no license exists."""
        return get_license_info()
