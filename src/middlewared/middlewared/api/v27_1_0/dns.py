from pydantic import Field

from middlewared.api.base import BaseModel, IPvAnyAddress

__all__ = ["DNSQueryItem"]


class DNSQueryItem(BaseModel):
    nameserver: IPvAnyAddress = Field(description="IP address of the DNS nameserver to query.")
