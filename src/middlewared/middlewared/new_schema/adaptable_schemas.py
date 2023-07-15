from .attribute import Attribute
from .exceptions import Error


class Any(Attribute):

    def to_json_schema(self, parent=None):
        return {
            'anyOf': [
                {'type': 'string'},
                {'type': 'integer'},
                {'type': 'boolean'},
                {'type': 'object'},
                {'type': 'array'},
            ],
            'nullable': self.null,
            **self._to_json_schema_common(parent),
        }


class Bool(Attribute):

    def clean(self, value):
        value = super().clean(value)
        if value is None:
            return value
        if not isinstance(value, bool):
            raise Error(self.name, 'Not a boolean')
        return value

    def to_json_schema(self, parent=None):
        return {
            'type': ['boolean', 'null'] if self.null else 'boolean',
            **self._to_json_schema_common(parent),
        }
