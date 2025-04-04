from middlewared.api.base import BaseModel, single_argument_result, IPvAnyAddress, NotRequired


__all__ = ["NetworkGeneralSummaryArgs", "NetworkGeneralSummaryResult",]


class NetworkGeneralSummaryIP(BaseModel):
    IPV4: list[str] = NotRequired
    IPV6: list[str] = NotRequired


class NetworkGeneralSummaryArgs(BaseModel):
    pass


@single_argument_result
class NetworkGeneralSummaryResult(BaseModel):
    ips: dict[str, NetworkGeneralSummaryIP]
    default_routes: list[IPvAnyAddress]
    nameservers: list[IPvAnyAddress]
