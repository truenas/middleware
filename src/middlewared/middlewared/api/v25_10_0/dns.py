from middlewared.api.base import BaseModel, IPvAnyAddress


class DNSQueryItem(BaseModel):
    nameserver: IPvAnyAddress
