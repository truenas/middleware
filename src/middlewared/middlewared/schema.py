import copy


class Error(Exception):

    def __init__(self, attribute, errmsg):
        self.attribute = attribute
        self.errmsg = errmsg

    def __str__(self):
        return '[{0}] {1}'.format(self.attribute, self.errmsg)


class EnumMixin(object):

    def __init__(self, *args, **kwargs):
        self.enum = kwargs.pop('enum', None)
        super(EnumMixin, self).__init__(*args, **kwargs)

    def clean(self, value):
        if self.enum is None:
            return value
        if not isinstance(value, (list, tuple)):
            tmp = [value]
        else:
            tmp = value
        for v in tmp:
            if v not in self.enum:
                raise Error(self.name, 'Invalid choice: {0}'.format(value))
        return value


class Attribute(object):

    def __init__(self, name, verbose=None, required=False, validators=None, default=None, register=False):
        self.name = name
        self.default = default
        self.required = required
        self.verbose = verbose or name
        self.validators = validators or []
        self.register = register

    def clean(self, value):
        return value

    def to_json_schema(self):
        """This method should return the json-schema v4 equivalent for the
        given attribute.
        """
        raise NotImplementedError("Attribute must implement to_json_schema method")

    def resolve(self, middleware):
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
        if self.register:
            middleware.add_schema(self)
        return self


class Str(EnumMixin, Attribute):

    def clean(self, value):
        value = super(Str, self).clean(value)
        if value is None and not self.required:
            return self.default
        if not isinstance(value, str):
            raise Error(self.name, 'Not a string')
        return value

    def to_json_schema(self):
        schema = {'title': self.verbose}
        if not self.required:
            schema['type'] = ['string', 'null']
        else:
            schema['type'] = 'string'
        if self.enum is not None:
            schema['enum'] = self.enum
        return schema


class Bool(Attribute):

    def __init__(self, *args, **kwargs):
        if 'default' not in kwargs:
            kwargs['default'] = False
        super(Bool, self).__init__(*args, **kwargs)

    def clean(self, value):
        if value is None and not self.required:
            return self.default
        if not isinstance(value, bool):
            raise Error(self.name, 'Not a boolean')
        return value

    def to_json_schema(self):
        return {
            'type': ['boolean', 'null'] if not self.required else 'boolean',
            'title': self.verbose,
        }


class Int(Attribute):

    def clean(self, value):
        if not isinstance(value, int):
            if isinstance(value, str) and value.isdigit():
                return int(value)
            raise Error(self.name, 'Not an integer')
        return value

    def to_json_schema(self):
        return {
            'type': ['integer', 'null'] if not self.required else 'integer',
            'title': self.verbose,
        }


class List(EnumMixin, Attribute):

    def __init__(self, *args, **kwargs):
        self.items = kwargs.pop('items', [])
        super(List, self).__init__(*args, **kwargs)

    def clean(self, value):
        value = super(List, self).clean(value)
        if value is None and not self.required:
            return self.default
        if not isinstance(value, list):
            raise Error(self.name, 'Not a list')
        if self.items:
            for index, v in enumerate(value):
                for i in self.items:
                    try:
                        value[index] = i.clean(v)
                        found = True
                    except Error as e:
                        found = e
                        break
                if self.items and found is not True:
                    raise Error(self.name, 'Item#{0} is not valid per list types: {1}'.format(index, found))
        return value

    def to_json_schema(self):
        schema = {'type': 'array', 'title': self.verbose}
        if self.required:
            schema['type'] = ['array', 'null']
        else:
            schema['type'] = 'array'
        if self.enum is not None:
            schema['enum'] = self.enum
        return schema

    def resolve(self, middleware):
        for index, i in enumerate(self.items):
            self.items[index] = i.resolve(middleware)
        if self.register:
            middleware.add_schema(self)
        return self


class Dict(Attribute):

    def __init__(self, name, *attrs, **kwargs):
        self.additional_attrs = kwargs.pop('additional_attrs', False)
        # Update property is used to disable requirement on all attributes
        # as well to not populate default values for not specified attributes
        self.update = kwargs.pop('update', False)
        super(Dict, self).__init__(name, **kwargs)
        self.attrs = {}
        for i in attrs:
            self.attrs[i.name] = i

    def clean(self, data):
        if data is None and not self.required:
            return {}

        self.errors = []
        if not isinstance(data, dict):
            raise Error(self.name, 'A dict was expected')

        for key, value in list(data.items()):
            if not self.additional_attrs:
                if key not in self.attrs:
                    raise Error(key, 'Field was not expected')

            attr = self.attrs.get(key)
            if not attr:
                continue

            data[key] = attr.clean(value)

        # Do not make any field and required and not populate default values
        if not self.update:
            for attr in list(self.attrs.values()):

                if attr.required and attr.name not in data:
                    raise Error(attr.name, 'This field is required')

                if attr.name not in data:
                    data[attr.name] = attr.default

        return data

    def to_json_schema(self):
        schema = {
            'type': 'object',
            'title': self.verbose,
            'properties': {},
            'additionalProperties': self.additional_attrs,
        }
        for name, attr in list(self.attrs.items()):
            schema['properties'][name] = attr.to_json_schema()
        return schema

    def resolve(self, middleware):
        for name, attr in list(self.attrs.items()):
            self.attrs[name] = attr.resolve(middleware)
        if self.register:
            middleware.add_schema(self)
        return self


class Ref(object):

    def __init__(self, name):
        self.name = name

    def resolve(self, middleware):
        schema = middleware.get_schema(self.name)
        if not schema:
            raise ValueError('Schema {0} does not exist'.format(self.name))
        return schema


class Patch(object):

    def __init__(self, name, newname, *patches):
        self.name = name
        self.newname = newname
        self.patches = patches

    def convert(self, spec):
        t = spec.pop('type')
        name = spec.pop('name')
        if t in ('int', 'integer'):
            return Int(name, **spec)
        elif t in ('str', 'string'):
            return Str(name, **spec)
        elif t in ('bool', 'boolean'):
            return Bool(name, **spec)
        elif t == 'dict':
            return Dict(name, **spec)
        raise ValueError('Unknown type: {0}'.format(spec['type']))

    def resolve(self, middleware):
        schema = middleware.get_schema(self.name)
        if not isinstance(schema, Dict):
            raise ValueError('Patch non-dict is not allowed')

        schema = copy.deepcopy(schema)
        schema.name = self.newname
        for operation, patch in self.patches:
            if operation == 'add':
                new = self.convert(dict(patch))
                schema.attrs[new.name] = new
            elif operation == 'rm':
                del schema.attrs[patch['name']]
            elif operation == 'attr':
                for key, val in list(patch.items()):
                    setattr(schema, key, val)
        if self.register:
            middleware.add_schema(schema)
        return schema


def resolver(middleware, f):
    if not callable(f):
        return
    if not hasattr(f, 'accepts'):
        return
    new_params = []
    for p in f.accepts:
        if isinstance(p, (Patch, Ref, Attribute)):
            new_params.append(p.resolve(middleware))
        else:
            raise ValueError('Invalid parameter definition {0}'.format(p))

    # FIXME: for some reason assigning params (f.accepts = new_params) does not work
    while f.accepts:
        f.accepts.pop()
    f.accepts.extend(new_params)


def accepts(*schema):
    def wrap(f):
        # Make sure number of schemas is same as method argument
        args_index = 1
        if hasattr(f, '_pass_app'):
            args_index += 1
        if hasattr(f, '_job'):
            args_index += 1
        assert len(schema) == f.__code__.co_argcount - args_index  # -1 for self

        def nf(*args, **kwargs):
            args = list(args)

            # Iterate over positional args first, excluding self
            i = 0
            for arg in args[args_index:]:
                args[i + args_index] = nf.accepts[i].clean(args[i + args_index])
                i += 1

            # Use i counter to map keyword argument to rpc positional
            for x in list(range(i + 1, f.__code__.co_argcount)):
                kwarg = f.__code__.co_varnames[x]
                if kwarg in kwargs:
                    kwargs[kwarg] = nf.accepts[i].clean(kwargs[kwarg])
                i += 1
            return f(*args, **kwargs)
        nf.__name__ = f.__name__
        nf.__doc__ = f.__doc__
        # Copy private attrs to new function so decorators can work on top of it
        # e.g. _pass_app
        for i in dir(f):
            if i.startswith('__'):
                continue
            if i.startswith('_'):
                setattr(nf, i, getattr(f, i))
        nf.accepts = list(schema)

        return nf
    return wrap
