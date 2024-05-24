import errno
import ipaddress
import os
import uuid
import re

try:
    import wbclient
except ImportError:
    # During fresh install of TrueNAS lookup of libwbclient.so.0
    # will fail without specifying an LD_LOOKUP_PATH within the
    # freshly extracted TrueNAS SCALE squashfs filesystem. If we
    # don't skip the ImportError then fresh SCALE install will fail.
    pass

from datetime import datetime, time, timezone
from ldap import dn
from urllib.parse import urlparse

from middlewared.service_exception import CallError, ValidationErrors

from .attribute import Attribute
from .enum import EnumMixin
from .exceptions import Error
from .utils import RESERVED_WORDS

# NetBIOS domain names allow using a dot "." to define a NetBIOS scope
# This is not true for NetBIOS computer names
RE_NETBIOSNAME = re.compile(r"^(?![0-9]*$)[a-zA-Z0-9-_!@#\$%^&\(\)'\{\}~]{1,15}$")
RE_NETBIOSDOM = re.compile(r"^(?![0-9]*$)[a-zA-Z0-9\.\-_!@#\$%^&\(\)'\{\}~]{1,15}$")


class Str(EnumMixin, Attribute):

    def __init__(self, *args, **kwargs):
        # Sqlite limits ( (2 ** 31) - 1 ) for storing text - https://www.sqlite.org/limits.html
        self.max_length = kwargs.pop('max_length', 1024) or (2 ** 31) - 1
        super().__init__(*args, **kwargs)

    def clean(self, value):
        value = super(Str, self).clean(value)
        if value is None:
            return value
        if isinstance(value, int) and not isinstance(value, bool):
            value = str(value)
        if not isinstance(value, str):
            raise Error(self.name, f'[{value}]: Not a string')
        if not self.empty and not value.strip():
            raise Error(self.name, 'Empty value not allowed')
        return value

    def to_json_schema(self, parent=None):
        schema = self._to_json_schema_common(parent)

        if self.null:
            schema['type'] = ['string', 'null']
        else:
            schema['type'] = 'string'

        if self.enum is not None:
            schema['enum'] = self.enum

        return schema

    def validate(self, value):
        if value is None:
            return value

        verrors = ValidationErrors()

        if value and len(str(value)) > self.max_length:
            verrors.add(self.name, f'The value may not be longer than {self.max_length} characters')

        verrors.check()

        return super().validate(value)


class Path(Str):

    def __init__(self, *args, **kwargs):
        self.forwarding_slash = kwargs.pop('forwarding_slash', True)
        super().__init__(*args, **kwargs)

    def clean(self, value):
        value = super().clean(value)

        if value is None:
            return value

        value = value.strip()

        if self.forwarding_slash:
            value = value.rstrip("/")
        else:
            value = value.strip("/")

        return os.path.normpath(value.strip())


class Password(Str):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **(kwargs | {'private': True}))


class SID(Str):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def clean(self, value):
        value = super().clean(value)

        if value is None:
            return value

        value = value.strip()
        return value.upper()

    def validate(self, value):
        if value is None:
            return value

        verrors = ValidationErrors()

        if not wbclient.sid_is_valid(value):
            verrors.add(
                self.name,
                'SID is malformed. See MS-DTYP Section 2.4 for SID type specifications. '
                'Typically SIDs refer to existing objects on the local or remote server '
                'and so an appropriate value should be queried prior to submitting to API '
                'endpoints.'
            )

        verrors.check()


class NetbiosName(Str):
    regex = RE_NETBIOSNAME

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def clean(self, value):
        value = super().clean(value)

        if value is None:
            return value

        value = value.strip()
        return value.upper()

    def validate(self, value):
        if value is None:
            return value

        verrors = ValidationErrors()
        if not self.regex.match(value):
            verrors.add(
                self.name,
                'Invalid NetBIOS name. NetBIOS names must be between 1 and 15 characters in '
                'length and may not contain the following characters: \\/:*?"<>|.'
            )

        if value.casefold() in RESERVED_WORDS:
            verrors.add(
                self.name,
                f'NetBIOS names may not be one of following reserved names: {", ".join(RESERVED_WORDS)}'
            )

        verrors.check()
        return super().validate(value)


class NetbiosDomain(NetbiosName):
    regex = RE_NETBIOSDOM


class Dataset(Path):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('empty', False)
        kwargs.setdefault('forwarding_slash', False)
        super().__init__(*args, **kwargs)


class HostPath(Path):

    def validate_internal(self, verrors, value):
        pass

    def validate(self, value):
        if value is None:
            return

        verrors = ValidationErrors()

        if value:
            if not os.path.exists(value):
                verrors.add(self.name, 'This path does not exist.', errno.ENOENT)
            else:
                self.validate_internal(verrors, value)

        verrors.check()

        return super().validate(value)


class Dir(HostPath):

    def validate_internal(self, verrors, value):
        if not os.path.isdir(value):
            verrors.add(self.name, 'This path is not a directory.', errno.ENOTDIR)


class File(HostPath):

    def validate_internal(self, verrors, value):
        if not os.path.isfile(value):
            verrors.add(self.name, 'This path is not a file.', errno.EISDIR)


class URI(Str):

    def validate(self, value):
        super().validate(value)
        verrors = ValidationErrors()
        uri = urlparse(value)
        if not all(getattr(uri, k) for k in ('scheme', 'netloc')):
            verrors.add(self.name, 'Not a valid URI')
        verrors.check()


class IPAddr(Str):

    excluded_addr_types = [
        'MULTICAST',
        'PRIVATE',
        'GLOBAL',
        'UNSPECIFIED',
        'RESERVED',
        'LOOPBACK',
        'LINK_LOCAL'
    ]

    def __init__(self, *args, **kwargs):
        self.cidr = kwargs.pop('cidr', False)
        self.network = kwargs.pop('network', False)
        self.network_strict = kwargs.pop('network_strict', False)
        self.address_types = kwargs.pop('excluded_address_types', [])

        self.v4 = kwargs.pop('v4', True)
        self.v6 = kwargs.pop('v6', True)

        if self.v4 and self.v6:
            if self.network:
                self.factory = ipaddress.ip_network
            elif self.cidr:
                self.factory = ipaddress.ip_interface
            else:
                self.factory = ipaddress.ip_address
        elif self.v4:
            if self.network:
                self.factory = ipaddress.IPv4Network
            elif self.cidr:
                self.factory = ipaddress.IPv4Interface
            else:
                self.factory = ipaddress.IPv4Address
        elif self.v6:
            if self.network:
                self.factory = ipaddress.IPv6Network
            elif self.cidr:
                self.factory = ipaddress.IPv6Interface
            else:
                self.factory = ipaddress.IPv6Address
        else:
            raise ValueError('Either IPv4 or IPv6 should be allowed')

        self.allow_zone_index = kwargs.pop('allow_zone_index', False)

        super(IPAddr, self).__init__(*args, **kwargs)

    def __check_permitted_addr_types(self, value):
        if not self.address_types:
            return

        to_check = self.factory(value)

        if isinstance(to_check, (ipaddress.IPv4Interface, ipaddress.IPv6Interface)):
            to_check = to_check.ip

        for addr_type in self.address_types:
            if addr_type not in self.excluded_addr_types:
                raise CallError(
                    f'INTERNAL ERROR: {addr_type} not in supported types. '
                    'This indicates a programming error in API endpoint.'
                )

            if to_check.__getattribute__(f'is_{addr_type.lower()}'):
                raise ValueError(
                    f'{str(to_check)}: {addr_type.lower()} addresses are not permitted.'
                )

    def clean(self, value):
        value = super().clean(value)

        if value:
            try:
                if self.network:
                    value = str(self.factory(value, strict=self.network_strict))
                else:
                    if self.cidr and '/' not in value:
                        raise ValueError(
                            'Specified address should be in CIDR notation, e.g. 192.168.0.2/24'
                        )

                    zone_index = None
                    if self.allow_zone_index and '%' in value:
                        value, zone_index = value.rsplit('%', 1)

                    addr = self.factory(value)

                    if zone_index is not None and not isinstance(addr, ipaddress.IPv6Address):
                        raise ValueError('Zone index is allowed only for IPv6 addresses')

                    value = str(addr)
                    if zone_index is not None:
                        value += f'%{zone_index}'

                self.__check_permitted_addr_types(value)

            except ValueError as e:
                raise Error(self.name, str(e))

        return value

    def validate(self, value):
        if value is None:
            return value

        verrors = ValidationErrors()

        try:
            self.clean(value)
        except (Error, ValueError) as e:
            verrors.add(self.name, str(e))

        verrors.check()

        return super().validate(value)


class Time(Str):

    def clean(self, value):
        if isinstance(value, time):
            return value

        value = super(Time, self).clean(value)
        if value is None:
            return value

        try:
            hours, minutes = value.split(':')
        except ValueError:
            raise ValueError('Time should be in 24 hour format like "18:00"')
        else:
            try:
                return time(int(hours), int(minutes))
            except TypeError:
                raise ValueError('Time should be in 24 hour format like "18:00"')

    def validate(self, value):
        return super().validate(str(value))


class Datetime(Str):

    def clean(self, value):
        if isinstance(value, datetime):
            return value
        value = super().clean(value)
        if value is None:
            return value
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (TypeError, ValueError):
            raise ValueError('Invalid datetime specified')

    def validate(self, value):
        return super().validate(str(value))


class UUID(Str):

    def validate(self, value):
        if value is None:
            return

        verrors = ValidationErrors()
        try:
            if isinstance(value, int):
                uuid.UUID(int=value)
            else:
                uuid.UUID(value)
        except TypeError:
            verrors.add(self.name, 'Please supply a valid hex-formatted UUID string')
        except ValueError as e:
            verrors.add(self.name, e)

        verrors.check()

        return super().validate(value)


class UnixPerm(Str):

    def validate(self, value):
        if value is None:
            return

        try:
            mode = int(value, 8)
        except ValueError:
            raise ValueError('Not a valid integer. Must be between 000 and 777')

        if mode & 0o777 != mode:
            raise ValueError('Please supply a value between 000 and 777')

        return super().validate(value)


class LDAP_DN(Str):

    def validate(self, value):
        if value is None:
            return

        verrors = ValidationErrors()

        if not dn.is_dn(value):
            verrors.add(self.name, "Invalid LDAP DN specified.")

        verrors.check()
        return super().validate(value)
