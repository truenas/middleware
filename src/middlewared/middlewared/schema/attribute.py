import copy
import json
import textwrap

from middlewared.service_exception import ValidationErrors
from .exceptions import Error
from .utils import NOT_PROVIDED, REDACTED_VALUE


class Attribute:

    def __init__(
        self, name='', title=None, description=None, required=False, null=False, empty=True, private=False,
        validators=None, register=False, hidden=False, editable=True, example=None, **kwargs
    ):
        self.name = name
        self.has_default = 'default' in kwargs and kwargs['default'] is not NOT_PROVIDED
        self.default = kwargs.pop('default', None)
        self.required = required
        self.null = null
        self.empty = empty
        self.private = private
        self.title = title or name
        self.description = description
        self.validators = validators or []
        self.register = register
        self.hidden = hidden
        self.editable = editable
        self.resolved = False
        if example:
            self.description = (description or '') + '\n' + textwrap.dedent('''
            Example(s):
            ```
            ''') + json.dumps(example, indent=4) + textwrap.dedent('''
            ```
            ''')
        # When a field is marked as non-editable, it must specify a default
        if not self.editable and not self.has_default:
            raise Error(self.name, 'Default value must be specified when attribute is marked as non-editable.')

        if kwargs:
            raise TypeError(f"Unexpected keyword arguments: {', '.join(map(repr, kwargs.keys()))}")

    def clean(self, value):
        if value is None and self.null is False:
            raise Error(self.name, 'null not allowed')
        if value is NOT_PROVIDED:
            if self.has_default:
                value = copy.deepcopy(self.default)
            else:
                raise Error(self.name, 'attribute required')
        if not self.editable and value != self.default:
            raise Error(self.name, 'Field is not editable.')
        return value

    def has_private(self):
        return self.private

    def dump(self, value):
        if self.private:
            return REDACTED_VALUE

        return value

    def validate(self, value):
        verrors = ValidationErrors()

        for validator in self.validators:
            try:
                validator(value)
            except ValueError as e:
                verrors.add(self.name, str(e))

        verrors.check()

    def to_json_schema(self, parent=None):
        """This method should return the json-schema v4 equivalent for the
        given attribute.
        """
        raise NotImplementedError("Attribute must implement to_json_schema method")

    def _to_json_schema_common(self, parent) -> dict:
        schema = {}

        schema['_name_'] = self.name

        if self.title:
            schema['title'] = self.title

        if self.description:
            schema['description'] = self.description

        if self.has_default:
            schema['default'] = self.default

        schema['_required_'] = self.required

        return schema

    def resolve(self, schemas):
        """
        After every plugin is initialized this method is called for every method param
        so that the real attribute is evaluated.
        e.g.
        @params(
            Patch('schema-name', 'new-name', ('add', {'type': 'string', 'name': test'})),
            Ref('schema-test'),
        )
        will resolve to:
        @params(
            Dict('new-name', ...)
            Dict('schema-test', ...)
        )
        """
        self.resolved = True
        if self.register:
            schemas.add(self)
        return self

    def copy(self):
        cp = copy.deepcopy(self)
        cp.register = False
        return cp
