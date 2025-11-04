import operator

from .schema import SchemaMixin
from middlewared.utils.jsonpath import JSON_PATH_PREFIX, json_path_parse
from sqlalchemy import func


def in_(col, value):
    has_nulls = None in value
    value = [v for v in value if v is not None]
    expr = col.in_(value)
    if has_nulls:
        expr = expr | (col == None)  # noqa
    return expr


def nin(col, value):
    has_nulls = None in value
    value = [v for v in value if v is not None]
    expr = ~col.in_(value)
    if has_nulls:
        expr = expr & (col != None)  # noqa
    return expr


class FilterMixin(SchemaMixin):
    def _filters_contains_foreign_key(self, filters):
        for f in filters:
            if not isinstance(f, (list, tuple)):
                raise ValueError('Filter must be a list or tuple: {0}'.format(f))
            if len(f) == 3:
                name, _, _ = f
                if any((x in name for x in ['__', '.'])):
                    return True
        return False

    def _filters_to_queryset(self, filters, table, prefix, aliases):
        opmap = {
            '=': operator.eq,
            '!=': operator.ne,
            '>': operator.gt,
            '>=': operator.ge,
            '<': operator.lt,
            '<=': operator.le,
            '~': lambda col, value: col.op('regexp')(value),
            'in': in_,
            'nin': nin,
            '^': lambda col, value: col.startswith(value),
            '$': lambda col, value: col.endswith(value),
        }

        rv = []
        for f in filters:
            if not isinstance(f, (list, tuple)):
                raise ValueError('Filter must be a list or tuple: {0}'.format(f))
            if len(f) == 3:
                name, op, value = f

                # Special handling for JSONPath, e.g. $.["foo.bar"] for sqlalchemy JSON data type
                # Sample filter: [['$.["svc_data"]["username"]', '=', 'mary']]
                #
                # WARNING: this capability doesn't exist for encrypted JSON fields.
                if name.startswith(JSON_PATH_PREFIX):
                    name, json_target = json_path_parse(name)
                    col = self._get_col(table, name, prefix)
                    # Set up JSON1 operation to extract JSON data for filtering
                    col = func.json_extract(col, json_target)
                elif matched := next((x for x in ['__', '.'] if x in name), False):
                    fk, name = name.split(matched, 1)
                    col = self._get_col(aliases[list(self._get_col(table, fk, prefix).foreign_keys)[0]], name, '')
                else:
                    col = self._get_col(table, name, prefix)

                if op not in opmap:
                    raise ValueError('Invalid operation: {0}'.format(op))

                q = opmap[op](col, value)
                rv.append(q)
            elif len(f) == 2:
                op, value = f
                if op == 'OR':
                    or_value = None
                    for value in self._filters_to_queryset(value, table, prefix, aliases):
                        if or_value is None:
                            or_value = value
                        else:
                            or_value |= value
                    rv.append(or_value)
                else:
                    raise ValueError('Invalid operation: {0}'.format(op))
            else:
                raise ValueError('Invalid filter {0}'.format(f))
        return rv
