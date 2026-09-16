from __future__ import annotations

import typing

from truenas_pylicensed.features import LicenseFeature

if typing.TYPE_CHECKING:
    from middlewared.main import Middleware
    from middlewared.service_exception import ValidationErrors


async def validate_sed_license(
    middleware: Middleware,
    verrors: ValidationErrors,
    location: str,
) -> None:
    """Reject enabling SED functionality on systems that are not entitled to it.

    SED requires TrueNAS hardware carrying a license with the SED feature key.

    `location` is the key the denial is reported under. Callers that build their own
    `ValidationErrors` pass a full schema path; a settings field validator passes the bare
    field name, because the schema is prefixed for it.
    """
    entitlement = await middleware.call2(middleware.services.truenas.entitlements.check, LicenseFeature.SED)
    if not entitlement.entitled:
        verrors.add(location, entitlement.message)
