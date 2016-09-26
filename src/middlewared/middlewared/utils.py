def django_modelobj_serialize(middleware, obj, extend=None):
    from django.db.models.fields.related import ForeignKey
    from freenasUI.contrib.IPAddressField import (
        IPAddressField, IP4AddressField, IP6AddressField
    )
    data = {}
    for field in obj._meta.fields:
        value = getattr(obj, field.name)
        if isinstance(field, (
            IPAddressField, IP4AddressField, IP6AddressField
        )):
            data[field.name] = str(value)
        elif isinstance(field, ForeignKey):
            data[field.name] = django_modelobj_serialize(middleware, value) if value is not None else value
        else:
            data[field.name] = value
    if extend:
        data = middleware.call(extend, data)
    return data


def filter_list(_list, filters=None, options=None):

    opmap = {
        '=': lambda x, y: x == y,
        '!=': lambda x, y: x != y,
    }

    if filters is None:
        filters = {}
    if options is None:
        options = {}

    rv = []
    if filters:
        for i in _list:
            for f in filters:
                if len(f) == 3:
                    name, op, value = f
                    if op not in opmap:
                        raise ValueError('Invalid operation: {}'.format(op))
                    if isinstance(i, dict):
                        source = i[name]
                    elif hasattr(i, '__encode__'):
                        source = i.__encode__()[name]
                    else:
                        source = getattr(i, name)
                    if opmap[op](source, value):
                        if options.get('get') is True:
                            return i
                        rv.append(i)
    else:
        rv = _list

    if options.get('count') is True:
        return len(rv)

    if options.get('get') is True:
        return rv[0]

    return rv
