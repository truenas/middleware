from typing import Literal, TypeAlias

__all__ = ["IscsiAuthType", "IscsiExtentBlockSize", "IscsiExtentRPM", "IscsiExtentType"]

IscsiAuthType: TypeAlias = Literal['NONE', 'CHAP', 'CHAP_MUTUAL']
IscsiExtentType: TypeAlias = Literal['DISK', 'FILE']
IscsiExtentBlockSize: TypeAlias = Literal[512, 1024, 2048, 4096]
IscsiExtentRPM: TypeAlias = Literal['UNKNOWN', 'SSD', '5400', '7200', '10000', '15000']
