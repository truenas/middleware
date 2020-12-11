import operator

from .schema import SchemaMixin


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

                if '__' in name:
                    fk, name = name.split('__', 1)
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
