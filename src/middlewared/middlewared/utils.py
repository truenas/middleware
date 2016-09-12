from django.db.models.fields.related import ForeignKey
from freenasUI.contrib.IPAddressField import (
    IPAddressField, IP4AddressField, IP6AddressField
)


def django_modelobj_serialize(middleware, obj, extend=None):
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
