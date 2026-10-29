from __future__ import annotations

from typing import TYPE_CHECKING

from truenas_pylicensed.features import LicenseFeature

from middlewared.api.current import ServiceOptions
from middlewared.common.license_delegate import LicenseDelegate

from .bucket_crud import audit_actions

if TYPE_CHECKING:
    from middlewared.api.current import SharingS3Entry
    from middlewared.main import Middleware


async def _reload_s3(d: LicenseDelegate) -> None:
    if await d.call2(d.s.service.started, "s3"):
        await (await d.call2(d.s.service.control, "RELOAD", "s3", ServiceOptions(ha_propagate=False))).wait(
            raise_error=True
        )


class S3VersioningLicenseDelegate(LicenseDelegate):
    feature = LicenseFeature.S3_VERSIONING
    services = frozenset({"s3"})

    async def alert_lines(self, in_grace: bool) -> list[str]:
        buckets: list[SharingS3Entry] = await self.middleware.call("sharing.s3.query")
        names = [bucket.name for bucket in buckets if bucket.versioning != "OFF" or bucket.object_lock]
        if not names:
            return []
        joined = ", ".join(sorted(names))
        if in_grace:
            return [
                f"S3: buckets {joined} with versioning or object lock stay writable until the next reboot or an "
                "administrator stop or restart of S3. After that they are read-only until the system is licensed "
                "for S3 versioning."
            ]
        return [
            f"S3: buckets {joined} with versioning or object lock are read-only because the system is not licensed "
            "for S3 versioning. They become writable again when the feature is licensed."
        ]

    async def on_grant(self) -> None:
        await _reload_s3(self)


class S3AuditLicenseDelegate(LicenseDelegate):
    feature = LicenseFeature.S3_AUDIT

    async def alert_lines(self, in_grace: bool) -> list[str]:
        cfg = await self.call2(self.s.s3.config)
        buckets: list[SharingS3Entry] = await self.middleware.call("sharing.s3.query")
        names = [
            bucket.name
            for bucket in buckets
            if audit_actions(bucket.audit if bucket.audit is not None else cfg.default_audit)
        ]
        if not names:
            return []
        return [
            f"S3 audit: auditing configured for buckets {', '.join(sorted(names))} is not recorded because the "
            "system is not licensed for S3 audit."
        ]

    async def on_grant(self) -> None:
        await _reload_s3(self)


async def setup(middleware: Middleware) -> None:
    await middleware.call2(
        middleware.services.truenas.entitlements.register_license_delegate, S3VersioningLicenseDelegate(middleware)
    )
    await middleware.call2(
        middleware.services.truenas.entitlements.register_license_delegate, S3AuditLicenseDelegate(middleware)
    )
