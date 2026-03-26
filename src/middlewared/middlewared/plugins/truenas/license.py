from middlewared.api import api_method
from middlewared.api.current import (
    TrueNASLicenseUploadArgs,
    TrueNASLicenseUploadResult,
    TrueNASLicenseInfoArgs,
    TrueNASLicenseInfoResult,
)
from middlewared.service import Service, ValidationError
from truenas_pylicensed import LicenseType

from .license_utils import (
    LICENSE_FILE,
    LicenseInfo,
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
        lic = upload_license(license_)
        if lic.type == LicenseType.ENTERPRISE_HA:
            try:
                self.middleware.call_sync("failover.ensure_remote_client")
            except Exception as e:
                # this is fatal because we can't determine what the remote ip address
                # is to so any failover.call_remote calls will fail
                raise ValidationError(
                    "truenas.license.updload",
                    f"Failed to determine remote heartbeat IP address: {e}",
                )

            try:
                self.middleware.call_sync(
                    "failover.call_remote", "failover.ensure_remote_client"
                )
            except Exception:
                # this is not fatal, so no reason to return early
                # it just means that any "failover.call_remote" calls initiated from the remote node
                # will fail but that shouldn't be happening anyways
                self.logger.warning(
                    "Remote node failed to determine this nodes heartbeat IP address",
                    exc_info=True,
                )

            try:
                self.middleware.call_sync("failover.send_small_file", LICENSE_FILE)
            except Exception:
                self.logger.warning(
                    "Failed to sync database to remote node", exc_info=True
                )

            try:
                self.middleware.call_sync(
                    "failover.call_remote", "etc.generate", ["rc"]
                )
            except Exception:
                self.logger.warning("etc.generate failed on standby", exc_info=True)

    @api_method(
        TrueNASLicenseInfoArgs,
        TrueNASLicenseInfoResult,
        roles=["READONLY_ADMIN"],
    )
    def info(self) -> LicenseInfo | None:
        """Returns the parsed license object, or null if no license exists."""
        return get_license_info()
