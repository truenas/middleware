"""Normalized license objects, identical whichever source produced them."""

from __future__ import annotations

import typing
from dataclasses import dataclass
from datetime import date

if typing.TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from truenas_pylicensed import LicenseType

__all__ = ("FeatureInfo", "LicenseInfo")


@dataclass(frozen=True, kw_only=True, slots=True)
class FeatureInfo:
    name: str
    """Feature key (e.g. "DEDUP", "SED").

    A plain str rather than a LicenseFeature: the daemon does not constrain
    feature keys on the wire, so an unrecognized key has to round-trip
    untouched.
    """
    start_date: date | None
    """Feature start date or None."""
    expires_at: date | None
    """Feature expiration date or None for perpetual."""
    source: str
    """How the feature was granted (e.g. "enterprise")."""
    type: str | None = None
    """Per-feature tier qualifier (e.g. SUPPORT type=GOLD), read by the proactive-support tier gate."""


@dataclass(frozen=True, kw_only=True, slots=True)
class LicenseInfo:
    # Unhashable because the container fields are MappingProxyType; None keeps the generated __eq__.
    __hash__ = None  # type: ignore[assignment]

    id: str
    """Unique UUID string for the license."""
    type: LicenseType
    """The license type."""
    model: str | None
    """Hardware model (e.g. "H30") for enterprise types, None otherwise."""
    support_expires_at: date | None
    """End of the support contract, or None when the license carries no support.

    This is the only expiry a license carries. A license itself does not expire;
    expiry is a property of individual features, and SUPPORT is the only one
    whose expiry anything acts on.
    """
    features: Mapping[str, FeatureInfo]
    """Licensed features, keyed by the feature name each one carries."""
    serials: Sequence[str]
    """System serial number(s) for hardware-bound licenses."""
    enclosures: Mapping[str, int]
    """Licensed enclosure models mapped to count."""
    contract_type: str | None
    """Support contract type."""

    def has_feature(self, name: str) -> bool:
        return name in self.features  # membership only; the feature's own expiry is not consulted

    def feature(self, name: str) -> FeatureInfo | None:
        return self.features.get(name)

    def feature_type(self, name: str) -> str | None:
        info = self.features.get(name)
        return info.type if info is not None else None

    def has_serial(self, serial: str) -> bool:
        return serial in self.serials

    def support_lapsed(self, today: date | None = None) -> bool:
        """A contract is in force through its end date, so the comparison is strict."""
        expires_at = self.support_expires_at
        return expires_at is not None and expires_at < (today or date.today())
