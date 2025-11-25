from middlewared.api.base import BaseModel, single_argument_result, IPvAnyAddress, NotRequired


__all__ = ["NetworkGeneralSummaryArgs", "NetworkGeneralSummaryResult",]


class NetworkGeneralSummaryIP(BaseModel):
    IPV4: list[str] = NotRequired
    """Array of IPv4 addresses assigned to this interface."""
    IPV6: list[str] = NotRequired
    """Array of IPv6 addresses assigned to this interface."""


class NetworkGeneralSummaryArgs(BaseModel):
    pass


@single_argument_result
class NetworkGeneralSummaryResult(BaseModel):
    ips: dict[str, NetworkGeneralSummaryIP]
    """Object mapping interface names to their IP address information."""
    default_routes: list[IPvAnyAddress]
    """Array of default gateway addresses."""
    nameservers: list[IPvAnyAddress]
    """Array of configured DNS server addresses."""
