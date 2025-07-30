from middlewared.api.base import BaseModel, IPvAnyAddress


__all__ = ["DNSQueryItem"]


class DNSQueryItem(BaseModel):
    nameserver: IPvAnyAddress
    """IP address of the DNS nameserver to query."""
