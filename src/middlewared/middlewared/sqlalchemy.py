import datetime

import isodate
from sqlalchemy import (
    Table, Column as _Column, ForeignKey, Index,
    Boolean, CHAR, DateTime as _DateTime, Integer, SmallInteger, String, Text, UniqueConstraint
)  # noqa
from sqlalchemy import JSON as NativeJSON  # noqa
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import relationship  # noqa
from sqlalchemy.types import UserDefinedType, TypeDecorator

from truenas_api_client import json

from middlewared.utils.pwenc import encrypt, decrypt


class Base(object):
    __table_args__ = {"sqlite_autoincrement": True}


Model = declarative_base(cls=Base)
Model.metadata.naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}


class Column(_Column):
    inherit_cache = True

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("nullable", False)
        super().__init__(*args, **kwargs)


class EncryptedText(UserDefinedType):
    cache_ok = True

    def get_col_spec(self, **kw):
        return "TEXT"

    def _bind_processor(self, value):
        if value is None:
            return None

        return encrypt(value) if value else ''

    def bind_processor(self, dialect):
        return self._bind_processor

    def _result_processor(self, value):
        if value is None:
            return None

        return decrypt(value) if value else ''

    def result_processor(self, dialect, coltype):
        return self._result_processor


class JSON(TypeDecorator):
    impl = Text
    cache_ok = True

    def __init__(self, type_=dict, encrypted=False):
        super().__init__()
        self.type = type_
        self.encrypted = encrypted

    def process_bind_param(self, value, dialect):
        if value is None:
            if self.type is not None:
                value = self.type()
        result = json.dumps(value)
        if self.encrypted:
            result = encrypt(result)
        return result

    def process_result_value(self, value, dialect):
        try:
            if self.encrypted:
                value = decrypt(value, _raise=True)
            return json.loads(value)
        except Exception:
            if self.type is not None:
                return self.type()


class MultiSelectField(UserDefinedType):
    cache_ok = True

    def get_col_spec(self, **kw):
        return "TEXT"

    def _bind_processor(self, value):
        if value is None:
            return None

        return ",".join(value)

    def bind_processor(self, dialect):
        return self._bind_processor

    def _result_processor(self, value):
        if value:
            try:
                return value.split(",")
            except Exception:
                pass

        return []

    def result_processor(self, dialect, coltype):
        return self._result_processor


class DateTime(TypeDecorator):
    impl = _DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and getattr(value, "tzinfo", None):
            return value.replace(tzinfo=None)

        return value

    def process_result_value(self, value, dialect):
        if value is not None and getattr(value, "tzinfo", None):
            return value.replace(tzinfo=None)

        return value


class Time(UserDefinedType):
    cache_ok = True

    def get_col_spec(self, **kw):
        return "TIME"

    def _bind_processor(self, value):
        if value is None:
            return None

        if isinstance(value, str):
            value = isodate.parse_time(value)

        return value.isoformat()

    def bind_processor(self, dialect):
        return self._bind_processor

    def _result_processor(self, value):
        try:
            return isodate.parse_time(value)
        except Exception:
            return datetime.time()

    def result_processor(self, dialect, coltype):
        return self._result_processor
