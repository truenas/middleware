from typing import Any

from truenas_pylicensed import verify

from middlewared.api import api_method
from middlewared.api.current import (
    EntitlementEntry,
    EntitlementFactsEntry,
    EntitlementsInfo,
    TrueNASEntitlementsCheckArgs,
    TrueNASEntitlementsCheckResult,
    TrueNASEntitlementsFactsArgs,
    TrueNASEntitlementsFactsResult,
    TrueNASEntitlementsInfoArgs,
    TrueNASEntitlementsInfoResult,
)
from middlewared.plugins.truenas.entitlement_usage import PROBES
from middlewared.service import CallError, Service, private
from middlewared.utils.entitlements import (
    POLICY,
    Entitlement,
    Reason,
    check_entitlement,
    get_entitlement,
    get_facts,
)
from middlewared.utils.hardware import get_hardware_info
from middlewared.utils.license import LicenseOrigin, describe_legacy_license


def _entry(entitlement: Entitlement) -> EntitlementEntry:
    """Project an engine decision onto its API representation.

    The engine is a pure package, and importing `middlewared.api.base` into it would break the
    `entitlements_layers` import contract. So `get_entitlement()` keeps returning the dataclass,
    and callers that cannot reach this service still get it. This function is the only place the
    two meet.

    `column` is not carried across. It is the matrix coordinate the facts resolved to, and
    publishing it would make the matrix's shape a contract.
    """
    return EntitlementEntry(
        entitled=entitlement.entitled,
        reason=entitlement.reason.value,
        message=entitlement.message,
    )


class TrueNASEntitlementsService(Service):
    class Config:
        namespace = "truenas.entitlements"
        cli_private = True

    @api_method(
        TrueNASEntitlementsCheckArgs,
        TrueNASEntitlementsCheckResult,
        roles=["SYSTEM_PRODUCT_READ"],
        check_annotations=True,
    )
    def check(self, feature: str) -> EntitlementEntry:
        """Return the entitlement for ``feature`` computed from current system facts.

        ``POLICY`` is keyed by StrEnum members, so a plain feature name looks up the same rule.
        """
        try:
            entitlement = get_entitlement(feature)
        except ValueError:
            # `POLICY` is the register of what this product gates, so a key it does not carry
            # is a decision rather than an error: nothing on this system restricts the feature.
            return EntitlementEntry(entitled=True, reason=Reason.NOT_GATED.value, message="")
        except Exception as e:
            raise CallError(f"Unable to determine entitlement for {feature!r}: {e}")

        return _entry(entitlement)

    @api_method(
        TrueNASEntitlementsInfoArgs,
        TrueNASEntitlementsInfoResult,
        roles=["SYSTEM_PRODUCT_READ"],
        check_annotations=True,
    )
    def info(self) -> EntitlementsInfo:
        """Return the entitlement decision for every gated feature."""
        # `get_facts()` is uncached and its license read is a round trip to the license daemon,
        # so read it once here rather than paying for that round trip once per feature.
        try:
            facts = get_facts()
        except Exception as e:
            raise CallError(f"Unable to determine entitlement facts: {e}")

        features: dict[str, EntitlementEntry] = {}
        # `POLICY` rather than the feature vocabulary: some license features deliberately
        # have no rule, and `check_entitlement` raises for a key it cannot resolve.
        for key in POLICY:
            features[str(key)] = _entry(check_entitlement(key, facts))

        return EntitlementsInfo(features=features)

    @api_method(
        TrueNASEntitlementsFactsArgs,
        TrueNASEntitlementsFactsResult,
        roles=["SYSTEM_PRODUCT_READ"],
        check_annotations=True,
    )
    def facts(self) -> EntitlementFactsEntry:
        """
        Return the hardware and license facts every entitlement decision is computed from.
        """
        # This is purely for UI to consume for branding purposes
        try:
            facts = get_facts()
        except Exception as e:
            raise CallError(f"Unable to determine entitlement facts: {e}")

        license_type = None
        if facts.license is not None and facts.license.origin is LicenseOrigin.ISSUED:
            license_type = facts.license.type.name

        return EntitlementFactsEntry(
            hardware_type="TRUENAS" if facts.hardware_class.is_appliance else "COMMUNITY",
            license_type=license_type,
        )

    @private
    def debug_info(self) -> dict[str, Any]:
        """Each section degrades to an error rather than raising: the systems this is collected
        from are the ones whose licensing is already misbehaving."""
        info: dict[str, Any] = {}

        try:
            hw = get_hardware_info()
            info["hardware"] = {
                "error": None,
                "platform": hw.platform.value,
                "hardware_class": hw.hardware_class.value,
                "chassis": hw.chassis,
                "ha_platform": hw.ha_platform,
                "is_ha_capable": hw.is_ha_capable,
            }
        except Exception as e:
            info["hardware"] = {"error": f"{type(e).__name__}: {e}"}

        try:
            status = verify()
            info["daemon"] = {
                "error": None,
                "valid": status.valid,
                "code": status.code.name,
                "message": status.error,
                "test": status.test,
                "reload_seq": status.reload_seq,
                "version": status.version,
                "issued_at": status.issued_at,
            }
        except Exception as e:
            info["daemon"] = {"error": f"{type(e).__name__}: {e}"}

        try:
            facts = get_facts()
            decisions: dict[str, Any] = {"error": None}
            for key in POLICY:
                entitlement = check_entitlement(key, facts)
                decisions[str(key)] = {
                    "entitled": entitlement.entitled,
                    "reason": str(entitlement.reason),
                    # `_entry` withholds this from the public API.
                    "column": entitlement.column,
                    "message": entitlement.message,
                }

            info["decisions"] = decisions
        except Exception as e:
            info["decisions"] = {"error": f"{type(e).__name__}: {e}"}

        try:
            info["legacy"] = describe_legacy_license()
        except Exception as e:
            info["legacy"] = {"error": f"{type(e).__name__}: {e}"}

        return info

    @private
    async def usage(self) -> dict[str, Any]:
        """Report every gated feature's entitlement alongside whether this system is configured to
        use it. `in_use` mirrors `entitled` for `SMB_FASTPATH` and `SUPPORT`, which leave no
        configuration behind to observe, and for any feature whose probe failed, which also carries
        an `error`. `CATALOG_ENTERPRISE_TRAIN` and `MISSION_CRITICAL` are set by the licensing hooks
        themselves, so they read as in use on almost every licensed system."""
        daemon_error: str | None = None
        try:
            features = (await self.call2(self.s.truenas.entitlements.info)).features
        except Exception as e:
            daemon_error = f"{type(e).__name__}: {e}"
            features = {
                str(key): EntitlementEntry(entitled=False, reason=Reason.NO_LICENSE.value, message="")
                for key in POLICY
            }

        usage: dict[str, Any] = {}
        for key, entitlement in features.items():
            in_use, error = await self._in_use(key, entitlement.entitled)
            usage[key] = {
                "entitled": entitlement.entitled,
                "reason": entitlement.reason,
                "message": entitlement.message,
                "in_use": in_use,
                "error": error or daemon_error,
            }

        return usage

    async def _in_use(self, key: str, entitled: bool) -> tuple[bool, str | None]:
        probe = PROBES.get(key)
        if probe is None:
            return entitled, None

        try:
            return await probe(self.context), None
        except Exception as e:
            self.logger.warning("%s: unable to determine whether feature is in use", key, exc_info=True)
            return entitled, f"{type(e).__name__}: {e}"
