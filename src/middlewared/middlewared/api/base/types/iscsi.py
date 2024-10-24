from typing import Literal, TypeAlias

__all__ = ["IscsiAuthType"]

IscsiAuthType: TypeAlias = Literal['NONE', 'CHAP', 'CHAP_MUTUAL']
