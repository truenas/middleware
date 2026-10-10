from __future__ import annotations

__all__ = ("domain_clock_advice",)


def domain_clock_advice(nts_servers: list[str], require_nts: bool) -> str:
    """What to add to an error about this system's clock disagreeing with a domain controller's, if anything.

    The usual remedy for such a member is to take its time from the domain controller. Domain controllers do not
    speak NTS, and chronyd ignores servers without NTS while any NTS server is configured (`authselectmode prefer`), or
    always while the system security configuration requires NTS (`require`), so the remedy would have no effect.
    """
    if require_nts:
        return (
            "NTS is required by the system security configuration, so this system cannot take its time from the domain "
            "controller. Correct the domain controller's clock."
        )

    if nts_servers:
        return (
            f"This system takes its time only from its NTS servers ({', '.join(nts_servers)}) and ignores servers "
            "without NTS, such as a domain controller. Correct the domain controller's clock, or remove the NTS "
            "servers or turn off their NTS option to use the domain controller as a time source."
        )

    return ""
