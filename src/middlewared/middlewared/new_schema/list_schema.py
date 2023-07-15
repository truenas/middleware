import copy

from middlewared.service_exception import ValidationErrors

from .attribute import Attribute
from .enum import EnumMixin
from .exceptions import Error
from .utils import REDACTED_VALUE


class List(EnumMixin, Attribute):

    def __init__(self, *args, **kwargs):
        self.items = kwargs.pop('items', [])
        self.unique = kwargs.pop('unique', False)
        if 'default' not in kwargs:
            kwargs['default'] = []
        super(List, self).__init__(*args, **kwargs)

    def clean(self, value):
        value = super(List, self).clean(value)
        if value is None:
            return copy.deepcopy(self.default)
        if not isinstance(value, (list, tuple)):
            raise Error(self.name, 'Not a list')
        if not self.empty and not value:
            raise Error(self.name, 'Empty value not allowed')
        if self.items:
            for index, v in enumerate(value):
                for i in self.items:
                    try:
                        tmpval = copy.deepcopy(v)
                        value[index] = i.clean(tmpval)
                        found = True
                        break
                    except (Error, ValidationErrors) as e:
                        found = e
                if self.items and found is not True:
                    raise Error(self.name, 'Item#{0} is not valid per list types: {1}'.format(index, found))
        return value

    def has_private(self):
        return self.private or any(item.has_private() for item in self.items)

    def dump(self, value):
        if self.private:
            return REDACTED_VALUE

        # No schema is specified for list items or a schema is specified but
        # does not contain any private values. In this situation it's safe to
        # simply dump the raw value
        if not self.items or not self.has_private():
            return value

        # In most cases we'll only have a single item and so avoid validation loop
        if len(self.items) == 1:
            return [self.items[0].dump(x) for x in value]

        # This is painful and potentially expensive. It would probably be best
        # if developers simply avoided designing APIs in this way.
        out_list = []
        for i in value:
            # Initialize the entry value to "private"
            # If for some reason we can't validate the item then obscure the entry
            # to prevent chance of accidental exposure of private data
            entry = REDACTED_VALUE
            for item in self.items:
                # the item.clean() method may alter the value and so we need to
                # make a deepcopy of it before validation
                to_validate = copy.deepcopy(i)
                try:
                    to_validate = item.clean(to_validate)
                    item.validate(to_validate)
                except Exception:
                    continue

                # Check whether we've already successfully validated this entry
                if entry != REDACTED_VALUE:
                    # more than one of schemas fit this bill.
                    # fail safe and make it private
                    entry = REDACTED_VALUE
                    break

                # dump the original value and not the one that has been cleaned
                entry = item.dump(i)

            out_list.append(entry)

        return out_list

    def validate(self, value):
        if value is None:
            return

        verrors = ValidationErrors()

        s = set()
        for i, v in enumerate(value):
            if self.unique:
                if isinstance(v, dict):
                    v = tuple(sorted(list(v.items())))
                if v in s:
                    verrors.add(f"{self.name}.{i}", "This value is not unique.")
                s.add(v)
            attr_verrors = ValidationErrors()
            for attr in self.items:
                try:
                    attr.validate(v)
                except ValidationErrors as e:
                    attr_verrors.add_child(f"{self.name}.{i}", e)
                else:
                    break
            else:
                verrors.extend(attr_verrors)

        verrors.check()

        super().validate(value)

    def to_json_schema(self, parent=None):
        schema = self._to_json_schema_common(parent)
        if self.null:
            schema['type'] = ['array', 'null']
        else:
            schema['type'] = 'array'
        schema['items'] = [i.to_json_schema(self) for i in self.items]
        return schema

    def resolve(self, schemas):
        for index, i in enumerate(self.items):
            if not i.resolved:
                self.items[index] = i.resolve(schemas)
        if self.register:
            schemas.add(self)
        self.resolved = True
        return self

    def copy(self):
        cp = super().copy()
        cp.items = []
        for item in self.items:
            cp.items.append(item.copy())
        return cp

