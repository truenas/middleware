import copy

from middlewared.service_exception import ValidationErrors

from .attribute import Attribute
from .exceptions import Error, ResolverError
from .utils import NOT_PROVIDED


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


class Ref:

    def __init__(self, name, new_name=None):
        self.schema_name = name
        self.name = new_name or name
        self.resolved = False

    def resolve(self, schemas):
        schema = schemas.get(self.schema_name)
        if not schema:
            raise ResolverError('Schema {0} does not exist'.format(self.schema_name))
        schema = schema.copy()
        schema.name = self.name
        schema.register = False
        schema.resolved = True
        self.resolved = True
        return schema

    def copy(self):
        return copy.deepcopy(self)


class OROperator:
    def __init__(self, *schemas, **kwargs):
        self.name = kwargs.get('name', '')
        self.title = kwargs.get('title') or self.name
        self.schemas = list(schemas)
        self.description = kwargs.get('description')
        self.resolved = False
        self.default = kwargs.get('default', None)
        self.has_default = 'default' in kwargs and kwargs['default'] is not NOT_PROVIDED
        self.private = kwargs.get('private', False)

    @property
    def required(self):
        for schema in filter(lambda s: hasattr(s, 'required'), self.schemas):
            if schema.required:
                return True
        return False

    def clean(self, value):
        if self.has_default and value == self.default:
            return copy.deepcopy(self.default)

        found = False
        final_value = value
        verrors = ValidationErrors()
        for index, i in enumerate(self.schemas):
            try:
                tmpval = copy.deepcopy(value)
                final_value = i.clean(tmpval)
            except (Error, ValidationErrors) as e:
                if isinstance(e, Error):
                    verrors.add(e.attribute, e.errmsg, e.errno)
                else:
                    verrors.extend(e)
            else:
                found = True
                break
        if found is not True:
            raise Error(self.name, f'Result does not match specified schema: {verrors}')
        return final_value

    def validate(self, value):
        verrors = ValidationErrors()
        attr_verrors = ValidationErrors()
        for attr in self.schemas:
            try:
                attr.validate(value)
            except TypeError:
                pass
            except ValidationErrors as e:
                attr_verrors.extend(e)
            else:
                break
        else:
            verrors.extend(attr_verrors)

        verrors.check()

    def to_json_schema(self, parent=None):
        return {
            'anyOf': [i.to_json_schema() for i in self.schemas],
            'nullable': False,
            '_name_': self.name,
            'description': self.description,
            '_required_': self.required,
        }

    def resolve(self, schemas):
        for index, i in enumerate(self.schemas):
            if not i.resolved:
                self.schemas[index] = i.resolve(schemas)
        self.resolved = True
        return self

    def copy(self):
        cp = copy.deepcopy(self)
        cp.register = False
        return cp

    def dump(self, value):
        value = copy.deepcopy(value)

        for schema in self.schemas:
            try:
                schema.clean(copy.deepcopy(value))
            except (Error, ValidationErrors):
                pass
            else:
                value = schema.dump(value)
                break

        return value

    def has_private(self):
        return self.private or any(schema.has_private() for schema in self.schemas)
