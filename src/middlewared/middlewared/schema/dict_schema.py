import copy
import collections

from middlewared.service_exception import ValidationErrors
from middlewared.utils import filter_list

from .attribute import Attribute
from .exceptions import Error
from .utils import NOT_PROVIDED, REDACTED_VALUE


class Dict(Attribute):

    def __init__(self, *attrs, **kwargs):
        # TODO: Let's please perhaps have name as a keyword argument when we add support for
        # optional name argument in accepts decorator
        if list(attrs) and isinstance(attrs[0], str):
            name = attrs[0]
            attrs = list(attrs[1:])
        else:
            name = ''
        self.additional_attrs = kwargs.pop('additional_attrs', False)
        self.conditional_defaults = kwargs.pop('conditional_defaults', {})
        self.private_keys = kwargs.pop('private_keys', [])
        self.strict = kwargs.pop('strict', False)
        # Update property is used to disable requirement on all attributes
        # as well to not populate default values for not specified attributes
        self.update = kwargs.pop('update', False)
        if 'default' not in kwargs:
            kwargs['default'] = {}
        super(Dict, self).__init__(name, **kwargs)

        self.attrs = {}
        for i in attrs:
            self.attrs[i.name] = i

        for k, v in self.conditional_defaults.items():
            if k not in self.attrs:
                raise ValueError(f'Specified attribute {k!r} not found.')
            for k_v in ('filters', 'attrs'):
                if k_v not in v:
                    raise ValueError(f'Conditional defaults must have {k_v} specified.')
            for attr in v['attrs']:
                if attr not in self.attrs:
                    raise ValueError(f'Specified attribute {attr} not found.')

        if self.strict:
            for attr in self.attrs.values():
                if attr.required:
                    if attr.has_default:
                        raise ValueError(
                            f'Attribute {attr.name} is required and has default value at the same time, '
                            'this is forbidden in strict mode'
                        )
                else:
                    if not attr.has_default:
                        raise ValueError(
                            f'Attribute {attr.name} is not required and does not have default value, '
                            'this is forbidden in strict mode'
                        )

    def has_private(self):
        return self.private or any(i.has_private() for i in self.attrs.values())

    def get_attrs_to_skip(self, data):
        skip_attrs = collections.defaultdict(set)
        check_data = self.get_defaults(data, {}, ValidationErrors(), False) if not self.update else data
        for attr, attr_data in filter(
            lambda k: not filter_list([check_data], k[1]['filters']), self.conditional_defaults.items()
        ):
            for k in attr_data['attrs']:
                skip_attrs[k].update({attr})

        return skip_attrs

    def clean(self, data):
        data = super().clean(data)

        if data is None:
            if self.null:
                return None

            return copy.deepcopy(self.default)

        if not isinstance(data, dict):
            raise Error(self.name, 'A dict was expected')

        verrors = ValidationErrors()
        for key, value in list(data.items()):
            if not self.additional_attrs:
                if key not in self.attrs:
                    verrors.add(f'{self.name}.{key}', 'Field was not expected')
                    continue

            attr = self.attrs.get(key)
            if not attr:
                continue

            data[key] = self._clean_attr(attr, value, verrors)

        # Do not make any field and required and not populate default values
        if not self.update:
            data.update(self.get_defaults(data, self.get_attrs_to_skip(data), verrors))

        verrors.check()

        return data

    def get_defaults(self, orig_data, skip_attrs, verrors, check_required=True):
        data = copy.deepcopy(orig_data)
        for attr in list(self.attrs.values()):
            if attr.name not in data and attr.name not in skip_attrs and (
                (check_required and attr.required) or attr.has_default
            ):
                data[attr.name] = self._clean_attr(attr, NOT_PROVIDED, verrors)
        return data

    def _clean_attr(self, attr, value, verrors):
        try:
            return attr.clean(value)
        except Error as e:
            verrors.add(f'{self.name}.{e.attribute}', e.errmsg, e.errno)
        except ValidationErrors as e:
            verrors.add_child(self.name, e)

    def dump(self, value):
        if self.private:
            return REDACTED_VALUE

        if not isinstance(value, dict):
            return value

        value = value.copy()
        for key in value:
            if key in self.private_keys:
                value[key] = REDACTED_VALUE
                continue

            attr = self.attrs.get(key)
            if not attr:
                continue

            value[key] = attr.dump(value[key])

        return value

    def validate(self, value):
        if value is None:
            return

        super().validate(value)
        verrors = ValidationErrors()

        for attr in self.attrs.values():
            if attr.name in value:
                try:
                    attr.validate(value[attr.name])
                except ValidationErrors as e:
                    verrors.add_child(self.name, e)

        verrors.check()

    def to_json_schema(self, parent=None):
        schema = {
            'type': 'object',
            'properties': {},
            'additionalProperties': self.additional_attrs,
            **self._to_json_schema_common(parent),
        }
        for name, attr in list(self.attrs.items()):
            schema['properties'][name] = attr.to_json_schema(parent=self)
        schema['_attrs_order_'] = list(self.attrs.keys())
        return schema

    def resolve(self, schemas):
        for name, attr in list(self.attrs.items()):
            if not attr.resolved:
                new_name = name
                self.attrs[new_name] = attr.resolve(schemas)
        if self.register:
            schemas.add(self)
        self.resolved = True
        return self

    def copy(self):
        cp = super().copy()
        cp.attrs = {}
        for name, attr in self.attrs.items():
            cp.attrs[name] = attr.copy()
        return cp
