import copy

from .convert_schema import convert_schema
from .dict_schema import Dict
from .exceptions import ResolverError


class Patch:

    def __init__(self, orig_name, newname, *patches, register=False):
        self.schema_name = orig_name
        self.name = newname
        self.patches = list(patches)
        self.register = register
        self.resolved = False

    def resolve(self, schemas):
        schema = schemas.get(self.schema_name)
        if not schema:
            raise ResolverError(f'Schema {self.schema_name} not found')
        elif not isinstance(schema, Dict):
            raise ValueError('Patch non-dict is not allowed')

        schema = schema.copy()
        schema.name = self.name
        if hasattr(schema, 'title'):
            schema.title = self.name
        for operation, patch in self.patches:
            if operation == 'replace':
                # This is for convenience where it's hard sometimes to change attrs in a large dict
                # with custom function(s) outlining the operation - it's easier to just replace the attr
                name = patch['name'] if isinstance(patch, dict) else patch.name
                self._resolve_internal(schema, schemas, 'rm', {'name': name})
                operation = 'add'
            self._resolve_internal(schema, schemas, operation, patch)
        if self.register:
            schemas.add(schema)
        schema.resolved = True
        self.resolved = True
        return schema

    def _resolve_internal(self, schema, schemas, operation, patch):
        if operation == 'add':
            if isinstance(patch, dict):
                new = convert_schema(dict(patch))
            else:
                new = copy.deepcopy(patch)
            schema.attrs[new.name] = new
        elif operation == 'rm':
            if patch.get('safe_delete') and patch['name'] not in schema.attrs:
                return
            del schema.attrs[patch['name']]
        elif operation == 'edit':
            attr = schema.attrs[patch['name']]
            if 'method' in patch:
                patch['method'](attr)
                schema.attrs[patch['name']] = attr.resolve(schemas)
        elif operation == 'attr':
            for key, val in list(patch.items()):
                setattr(schema, key, val)
