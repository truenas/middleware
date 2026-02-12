from __future__ import annotations

import datetime
from typing import Any

import isodate
from sqlalchemy import (
    Table, Column as _Column, ForeignKey, Index,
    Boolean, CHAR, DateTime as _DateTime, Integer, SmallInteger, String, Text, UniqueConstraint
)
from sqlalchemy import JSON as NativeJSON
from sqlalchemy.orm import declarative_base, relationship, Mapped
from sqlalchemy.types import UserDefinedType, TypeDecorator

from truenas_api_client import json

from middlewared.utils.pwenc import encrypt, decrypt

__all__ = ["Model", "Column", "Boolean", "ForeignKey", "Index", "Integer", "NativeJSON", "Mapped", "SmallInteger",
           "String", "Table", "Text", "UniqueConstraint", "relationship"]


class Base:
    __table_args__ = {"sqlite_autoincrement": True}


Model = declarative_base(cls=Base)
Model.metadata.naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}


# We deliberately not make this Generic as to avoid mypy checking our database models.
# We don't need type hints there, we're not using these models directly.
class Column(_Column):  # type: ignore[type-arg]
    inherit_cache = True

    def __init__(self, *args: Any, **kwargs: Any):
        kwargs.setdefault("nullable", False)
        super().__init__(*args, **kwargs)


class EncryptedText(UserDefinedType[str]):
    cache_ok = True

    def get_col_spec(self, **kw: Any) -> str:
        return "TEXT"

    def _bind_processor(self, value: str | None) -> str | None:
        if value is None:
            return None

        return encrypt(value) if value else ''

    def bind_processor(self, dialect: Any) -> Any:
        return self._bind_processor

    def _result_processor(self, value: str | None) -> str | None:
        if value is None:
            return None

        return decrypt(value) if value else ''

    def result_processor(self, dialect: Any, coltype: Any) -> Any:
        return self._result_processor


class JSON[T](TypeDecorator[T]):
    impl = Text
    cache_ok = True

    def __init__(self, type_: type[T], encrypted: bool = False) -> None:
        super().__init__()
        self.type = type_
        self.encrypted = encrypted

    def process_bind_param(self, value: T | None, dialect: Any) -> str:
        if value is None:
            if self.type is not None:
                value = self.type()
        result = json.dumps(value)
        if self.encrypted:
            result = encrypt(result)
        return result

    def process_result_value(self, value: Any, dialect: Any) -> T:
        if value is None:
            if self.type is not None:
                return self.type()

        assert isinstance(value, str)
        try:
            if self.encrypted:
                value = decrypt(value, _raise=True)
            return json.loads(value)  # type: ignore[no-any-return]
        except Exception:
            if self.type is not None:
                return self.type()


class MultiSelectField(UserDefinedType[str]):
    cache_ok = True

    def get_col_spec(self, **kw: Any) -> str:
        return "TEXT"

    def _bind_processor(self, value: list[str] | None) -> str | None:
        if value is None:
            return None

        return ",".join(value)

    def bind_processor(self, dialect: Any) -> Any:
        return self._bind_processor

    def _result_processor(self, value: str) -> list[str]:
        if value:
            try:
                return value.split(",")
            except Exception:
                pass

        return []

    def result_processor(self, dialect: Any, coltype: Any) -> Any:
        return self._result_processor


class DateTime(TypeDecorator[datetime.datetime]):
    impl = _DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime.datetime | None, dialect: Any) -> datetime.datetime | None:
        if value is not None and getattr(value, "tzinfo", None):
            return value.replace(tzinfo=None)

        return value

    def process_result_value(self, value: datetime.datetime | None, dialect: Any) -> datetime.datetime | None:
        if value is not None and getattr(value, "tzinfo", None):
            return value.replace(tzinfo=None)

        return value


class Time(UserDefinedType[datetime.time]):
    cache_ok = True

    def get_col_spec(self, **kw: Any) -> str:
        return "TIME"

    def _bind_processor(self, value: datetime.time | str | None) -> str | None:
        if value is None:
            return None

        if isinstance(value, str):
            parsed = isodate.parse_time(value)
        else:
            parsed = value

        return parsed.isoformat()  # type: ignore[no-any-return]

    def bind_processor(self, dialect: Any) -> Any:
        return self._bind_processor

    def _result_processor(self, value: str) -> datetime.time:
        try:
            return isodate.parse_time(value)  # type: ignore[no-any-return]
        except Exception:
            return datetime.time()

    def result_processor(self, dialect: Any, coltype: Any) -> Any:
        return self._result_processor
