from middlewared.api.base import BaseModel, IPvAnyAddress


__all__ = ["DNSQueryItem"]


class DNSQueryItem(BaseModel):
    nameserver: IPvAnyAddress
