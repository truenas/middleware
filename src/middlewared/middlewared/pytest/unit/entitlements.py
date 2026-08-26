"""Facts builders and live-engine stand-ins for `truenas.entitlements` in unit tests.

Kept out of `middleware.py` on purpose: `TrueNASEntitlementsCheckEntitlement` drags
`middlewared.api.current` and `middlewared.service` onto the import path of every test that
touches the fake middleware, and `middleware.py` is imported by nearly all of them.
"""

from datetime import date

from truenas_pylicensed import LicenseType

from middlewared.api.current import EntitlementEntry
from middlewared.plugins.truenas.entitlements import TrueNASEntitlementsCheckEntitlement
from middlewared.utils.entitlements import EntitlementFacts, HardwareClass, Reason, check_entitlement
from middlewared.utils.license import FeatureInfo, LicenseInfo


def make_license(
    *,
    feature_names: tuple[str, ...] = (),
    type_: LicenseType = LicenseType.ENTERPRISE_SINGLE,
    model: str | None = "H10",
    expires_at: date | None = None,
    support_type: str | None = None,
) -> LicenseInfo:
    features = {
        name: FeatureInfo(
            name=name,
            start_date=None,
            expires_at=expires_at,
            source="enterprise",
            type=support_type if name == "SUPPORT" else None,
        )
        for name in feature_names
    }
    return LicenseInfo(
        id="test-license",
        type=type_,
        model=model,
        support_expires_at=expires_at,
        features=features,
        serials=("TEST-000001",),
        enclosures={},
        contract_type=support_type,
    )


def make_facts(
    *,
    hardware_class: HardwareClass,
    license: LicenseInfo | None = None,
) -> EntitlementFacts:
    return EntitlementFacts(
        hardware_class=hardware_class,
        license=license,
    )


def facts_for_column(feature: str, column: str) -> EntitlementFacts:
    hardware_class = HardwareClass.TRUENAS_HW if column in ("HW", "HW+L", "HW+K") else HardwareClass.GENERIC
    if column in ("CE", "HW"):
        license = None
    elif column in ("HW+K", "CE+K"):
        license = make_license(feature_names=(feature,))
    else:  # HW+L / CE+L: licensed, but without this feature's key
        license = make_license(feature_names=())
    return make_facts(hardware_class=hardware_class, license=license)


def install_entitlements(middleware, facts) -> list[str]:
    """Point truenas.entitlements.check and .feature at the live engine over `facts`.

    Returns the keys asked about, in call order, so a test can still assert which feature a
    gate names -- and that a gate it should not reach was not consulted.
    """
    checked: list[str] = []

    def check(feature):
        checked.append(feature)
        # Deliberately unguarded: the engine raises ValueError for an unruled key and so does
        # production's `check`. Swallowing it would let a gate name a feature POLICY lacks.
        entitlement = check_entitlement(feature, facts)
        return TrueNASEntitlementsCheckEntitlement(
            entitled=entitlement.entitled,
            reason=entitlement.reason,
            column=entitlement.column,
            message=entitlement.message,
        )

    def feature(name):
        checked.append(name)
        # Mirrors TrueNASEntitlementsService.feature, which does NOT raise: over the public
        # endpoint an unruled key means "nothing gates this", not "error".
        try:
            entitlement = check_entitlement(name, facts)
        except ValueError:
            return EntitlementEntry(entitled=True, reason=Reason.NOT_GATED, message="")
        return EntitlementEntry(
            entitled=entitlement.entitled,
            reason=entitlement.reason,
            message=entitlement.message,
        )

    middleware.services.truenas.entitlements.check = check
    middleware.services.truenas.entitlements.feature = feature
    return checked


def install_entitlements_for_column(middleware, feature, column) -> list[str]:
    return install_entitlements(middleware, facts_for_column(feature, column))
