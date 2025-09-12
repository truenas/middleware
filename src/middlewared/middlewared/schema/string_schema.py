from middlewared.service_exception import ValidationErrors
from .attribute import Attribute
from .enum import EnumMixin
from .exceptions import Error


class Str(EnumMixin, Attribute):

    def __init__(self, *args, **kwargs):
        # Sqlite limits ( (2 ** 31) - 1 ) for storing text - https://www.sqlite.org/limits.html
        self.max_length = kwargs.pop('max_length', 1024) or (2 ** 31) - 1
        super().__init__(*args, **kwargs)

    def clean(self, value):
        value = super(Str, self).clean(value)
        if value is None:
            return value
        if isinstance(value, int) and not isinstance(value, bool):
            value = str(value)
        if not isinstance(value, str):
            raise Error(self.name, 'Not a string')
        if not self.empty and not value.strip():
            raise Error(self.name, 'Empty value not allowed')
        return value

    def to_json_schema(self, parent=None):
        schema = self._to_json_schema_common(parent)

        if self.null:
            schema['type'] = ['string', 'null']
        else:
            schema['type'] = 'string'

        if self.enum is not None:
            schema['enum'] = self.enum

        return schema

    def validate(self, value):
        if value is None:
            return value

        verrors = ValidationErrors()

        if value and len(str(value)) > self.max_length:
            verrors.add(self.name, f'The value may not be longer than {self.max_length} characters')

        verrors.check()

        return super().validate(value)
