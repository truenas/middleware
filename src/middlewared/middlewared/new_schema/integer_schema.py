import contextlib

from datetime import datetime

from .attribute import Attribute
from .enum import EnumMixin
from .exceptions import Error


class Int(EnumMixin, Attribute):

    def clean(self, value):
        value = super(Int, self).clean(value)
        if value is None or (not isinstance(value, bool) and isinstance(value, int)):
            return value
        elif isinstance(value, str):
            with contextlib.suppress(ValueError):
                return int(value)

        raise Error(self.name, 'Not an integer')

    def to_json_schema(self, parent=None):
        return {
            'type': ['integer', 'null'] if self.null else 'integer',
            **self._to_json_schema_common(parent),
        }


class Timestamp(Int):

    def validate(self, value):
        super().validate(value)
        if value is None:
            return value

        try:
            datetime.fromtimestamp(value)
        except ValueError:
            raise Error(self.name, 'Not a valid timestamp')


class Float(EnumMixin, Attribute):

    def clean(self, value):
        value = super(Float, self).clean(value)
        if value is None and not self.required:
            return self.default
        try:
            # float(False) = 0.0
            # float(True) = 1.0
            if isinstance(value, bool):
                raise TypeError()
            return float(value)
        except (TypeError, ValueError):
            raise Error(self.name, 'Not a floating point number')

    def to_json_schema(self, parent=None):
        return {
            'type': ['float', 'null'] if self.null else 'float',
            **self._to_json_schema_common(parent),
        }
