"""Policy other plugins attach to zfs.resource.set.

A delegate declares the resource types and touched native properties it cares about. It validates into the same
`ValidationErrors` as the intrinsic rules before anything is written and runs its side effects once the write has
succeeded.
"""

from __future__ import annotations

import typing

from middlewared.service_exception import ValidationError, ValidationErrors

from .set_rules import SETTABLE_PROPERTIES, SetContext

if typing.TYPE_CHECKING:
    from collections.abc import Iterable
    import logging

    from middlewared.api.current import ZFSResourceEntry
    from middlewared.main import Middleware

__all__ = (
    "RESOURCE_TYPES",
    "ZFSResourceDelegate",
    "participating",
    "run_after",
    "run_validate",
    "validate_delegate",
)

RESOURCE_TYPES = frozenset({"FILESYSTEM", "VOLUME"})


class ZFSResourceDelegate:
    name: typing.ClassVar[str]
    types: typing.ClassVar[frozenset[str]]
    triggers: typing.ClassVar[frozenset[str]]

    def __init__(self, middleware: Middleware) -> None:
        self.middleware = middleware

    async def validate_set(self, state: SetContext, verrors: ValidationErrors) -> None:
        """Add what is wrong with the request to `verrors`. Also runs for a dry run, so it must change nothing."""

    async def after_set(self, state: SetContext, entry: ZFSResourceEntry) -> None:
        """React to a successful write. `entry` is what the write read back."""


def validate_delegate(delegate: ZFSResourceDelegate) -> None:
    """Raise `ValueError` unless `delegate` names itself and declares only types and triggers `set` knows."""
    if not delegate.name:
        raise ValueError(f"{type(delegate).__name__}: a zfs.resource delegate must have a name")
    if unknown := delegate.types - RESOURCE_TYPES:
        raise ValueError(f"{delegate.name}: unknown resource types {sorted(unknown)}")
    if unknown := delegate.triggers - SETTABLE_PROPERTIES:
        raise ValueError(f"{delegate.name}: triggers are not settable properties: {sorted(unknown)}")


def participating(delegates: Iterable[ZFSResourceDelegate], touched: frozenset[str]) -> list[ZFSResourceDelegate]:
    """The delegates whose triggers the request touches, ordered by name."""
    return sorted((delegate for delegate in delegates if delegate.triggers & touched), key=lambda d: d.name)


async def run_validate(
    delegates: Iterable[ZFSResourceDelegate], state: SetContext, verrors: ValidationErrors, logger: logging.Logger
) -> list[tuple[str, Exception]]:
    """Run each delegate's `validate_set`, adding what they find to `verrors`. Never raises.

    A delegate that fails with anything but a validation error is logged and returned as `(delegate name,
    exception)` so the caller can refuse the request once everything else has had its say.
    """
    failures: list[tuple[str, Exception]] = []
    for delegate in delegates:
        try:
            await delegate.validate_set(state, verrors)
        except ValidationError as e:
            verrors.add_validation_error(e)
        except ValidationErrors as e:
            for error in e.errors:
                verrors.add_validation_error(error)
        except Exception as e:
            logger.error("%s: delegate %r validate_set failed", state.path, delegate.name, exc_info=True)
            failures.append((delegate.name, e))
    return failures


async def run_after(
    delegates: Iterable[ZFSResourceDelegate], state: SetContext, entry: ZFSResourceEntry, logger: logging.Logger
) -> None:
    """Run each delegate's `after_set` in turn. A failure is logged and never reaches the caller of the write."""
    for delegate in delegates:
        try:
            await delegate.after_set(state, entry)
        except Exception:
            logger.error("%s: delegate %r after_set failed", state.path, delegate.name, exc_info=True)
