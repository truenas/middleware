from ipaddr import _IPAddrBase, IPAddress, IPNetwork

from django.core.exceptions import ValidationError
from django.db import models

from dojango import forms
from dojango.forms import widgets

from south.modelsinspector import add_introspection_rules
add_introspection_rules([],
    ["^freenasUI\.contrib\.IPAddressField\.IPAddressField"])
add_introspection_rules([],
    ["^freenasUI\.contrib\.IPAddressField\.IP4AddressField"])
add_introspection_rules([],
    ["^freenasUI\.contrib\.IPAddressField\.IP6AddressField"])


class IPNetworkWidget(widgets.TextInput):
    def render(self, name, value, attrs=None):
        if isinstance(value, _IPAddrBase):
            value = u'%s' % value
        return super(IPNetworkWidget, self).render(name, value, attrs)


class IPNetworkManager(models.Manager):
    use_for_related_fields = True

    def __init__(self, qs_class=models.query.QuerySet):
        self.queryset_class = qs_class
        super(IPNetworkManager, self).__init__()

    def get_queryset(self):
        return self.queryset_class(self.model)

    def __getattr__(self, attr, *args):
        try:
            return getattr(self.__class__, attr, *args)
        except AttributeError:
            return getattr(self.get_queryset(), attr, *args)


class IPNetworkQuerySet(models.query.QuerySet):

    net = None

    def network(self, key, value):
        if not isinstance(value, _IPAddrBase):
            value = IPNetwork(value)
        self.net = (key, value)
        return self

    def iterator(self):
        for obj in super(IPNetworkQuerySet, self).iterator():
            try:
                net = IPNetwork(getattr(obj, self.net[0]))
            except (ValueError, TypeError):
                pass
            else:
                if not self.net[1] in net:
                    continue
            yield obj

    @classmethod
    def as_manager(cls, ManagerClass=IPNetworkManager):
        return ManagerClass(cls)


class IPNetworkField(models.Field):
    __metaclass__ = models.SubfieldBase
    description = "IP Network Field with CIDR support"
    empty_strings_allowed = False

    def db_type(self, connection):
        return 'varchar(45)'

    def to_python(self, value):
        if not value:
            return ""

        if isinstance(value, _IPAddrBase):
            return value

        try:
            return IPNetwork(value.encode('latin-1'))
        except Exception, e:
            raise ValidationError("Invalid IP address: %s" % e)

    def get_prep_lookup(self, lookup_type, value):
        if lookup_type == 'exact':
            return self.get_prep_value(value)
        elif lookup_type == 'in':
            return [self.get_prep_value(v) for v in value]
        else:
            raise TypeError('Lookup type %r not supported.' \
                % lookup_type)

    def get_prep_value(self, value):
        if isinstance(value, _IPAddrBase):
            value = '%s' % value
        return unicode(value)

    def formfield(self, **kwargs):
        defaults = {
            'form_class': IPAddressFormField,
            'widget': IPNetworkWidget,
        }
        defaults.update(kwargs)
        return super(IPNetworkField, self).formfield(**defaults)


class IPAddressFormFieldBase(forms.CharField):
    def to_python(self, value):
        if not value:
            return ""

        if isinstance(value, _IPAddrBase):
            return value

        if value == "None":
            return ""
        else:
            try:
                return IPAddress(value.encode('latin-1'))
            except Exception, e:
                raise ValidationError("Invalid IP address: %s" % e)


class IPAddressFormField(IPAddressFormFieldBase):
    def validate(self, value):
        super(IPAddressFormField, self).validate(value)


class IP4AddressFormField(IPAddressFormFieldBase):
    def to_python(self, value):
        if not value:
            return ""

        if isinstance(value, _IPAddrBase):
            return value

        if value == "None":
            return ""
        else:
            try:
                return IPAddress(value.encode('latin-1'), version=4)
            except Exception, e:
                raise ValidationError("Invalid IPv4 address: %s" % e)

    def validate(self, value):
        super(IP4AddressFormField, self).validate(value)


class IP6AddressFormField(IPAddressFormFieldBase):
    def to_python(self, value):
        if not value:
            return ""

        if isinstance(value, _IPAddrBase):
            return value

        if value == "None":
            return ""
        else:
            try:
                return IPAddress(value.encode('latin-1'), version=6)
            except Exception, e:
                raise ValidationError("Invalid IPv6 address: %s" % e)

    def validate(self, value):
        super(IP6AddressFormField, self).validate(value)


class IPAddressFieldBase(models.Field):
    description = "IP Address Field with IPv6 support"

    def db_type(self, connection):
        return 'varchar(42)'

    def to_python(self, value):
        if not value:
            return ""

        if isinstance(value, _IPAddrBase):
            return value

        if value == "None":
            return ""
        else:
            return IPAddress(value.encode('latin-1'))

    def get_prep_lookup(self, lookup_type, value):
        if lookup_type == 'exact':
            return self.get_prep_value(value)
        elif lookup_type == 'in':
            return [self.get_prep_value(v) for v in value]
        elif lookup_type == 'isnull':
            return self.get_prep_value(value)
        else:
            raise TypeError('Lookup type %r not supported.' \
                % lookup_type)

    def get_prep_value(self, value):
        if isinstance(value, _IPAddrBase):
            value = '%s' % value
        return unicode(value)


class IPAddressField(IPAddressFieldBase):
    __metaclass__ = models.SubfieldBase

    def formfield(self, **kwargs):
        defaults = {
            'form_class': IPAddressFormField,
            'widget': IPNetworkWidget,
        }
        defaults.update(kwargs)
        return super(IPAddressField, self).formfield(**defaults)


class IP4AddressField(IPAddressFieldBase):
    __metaclass__ = models.SubfieldBase
    description = "IPv4 Address Field"

    def to_python(self, value):
        if not value:
            return ""

        if isinstance(value, _IPAddrBase):
            return value

        if value == "None":
            return ""
        else:
            return IPAddress(value.encode('latin-1'), version=4)

    def formfield(self, **kwargs):
        defaults = {
            'form_class': IP4AddressFormField,
            'widget': IPNetworkWidget,
        }
        defaults.update(kwargs)
        return super(IP4AddressField, self).formfield(**defaults)


class IP6AddressField(IPAddressFieldBase):
    __metaclass__ = models.SubfieldBase
    description = "IPv6 Address Field"

    def to_python(self, value):
        if not value:
            return ""

        if isinstance(value, _IPAddrBase):
            return value

        if value == "None":
            return ""
        else:
            return IPAddress(value.encode('latin-1'), version=6)

    def formfield(self, **kwargs):
        defaults = {
            'form_class': IP6AddressFormField,
            'widget': IPNetworkWidget,
        }
        defaults.update(kwargs)
        return super(IP6AddressField, self).formfield(**defaults)
