from pydantic import Field

from middlewared.api.base import BaseModel, IPvAnyAddress, NotRequired, single_argument_result

__all__ = ["NetworkGeneralSummaryArgs", "NetworkGeneralSummaryResult",]


class NetworkGeneralSummaryIP(BaseModel):
    IPV4: list[str] = Field(default=NotRequired, description="Array of IPv4 addresses assigned to this interface.")
    IPV6: list[str] = Field(default=NotRequired, description="Array of IPv6 addresses assigned to this interface.")


class NetworkGeneralSummaryArgs(BaseModel):
    pass


@single_argument_result
class NetworkGeneralSummaryResult(BaseModel):
    ips: dict[str, NetworkGeneralSummaryIP] = Field(
        description="Object mapping interface names to their IP address information.",
    )
    default_routes: list[IPvAnyAddress] = Field(description="Array of default gateway addresses.")
    nameservers: list[IPvAnyAddress] = Field(description="Array of configured DNS server addresses.")
