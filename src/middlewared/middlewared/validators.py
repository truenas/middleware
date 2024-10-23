from datetime import time
import ipaddress
import os
import re
from urllib.parse import urlparse
import uuid
from string import digits, ascii_uppercase, ascii_lowercase, punctuation
from pathlib import Path

from middlewared.utils import filters
from middlewared.utils.filesystem.constants import ZFSCTL
from middlewared.utils.path import path_location
from zettarepl.snapshot.name import validate_snapshot_naming_schema

RE_MAC_ADDRESS = re.compile(r"^([0-9A-Fa-f]{2}[:-]?){5}([0-9A-Fa-f]{2})$")
filters_obj = filters()
validate_filters = filters_obj.validate_filters
validate_options = filters_obj.validate_options


class ValidatorBase:
    """The base validator class to be inherited by all validators"""
    def __call__(self, *args, **kwargs):
        raise NotImplementedError()


class Email(ValidatorBase):
    def __init__(self, empty=False):
        assert isinstance(empty, bool)
        self.empty = empty
        # https://www.rfc-editor.org/rfc/rfc5321#section-4.5.3.1.3
        # (subtract 2 because path portion of email is separated
        # by enclosing "<" which we cannot control)
        self.max_path = 254

    def __call__(self, value):
        if value is None or (self.empty and not value):
            return
        elif len(value) > self.max_path:
            raise ValueError("Maximum length is {self.max_path} characters.")
        else:
            right_most_atsign = value.rfind("@")
            if right_most_atsign == -1:
                raise ValueError("Missing '@' symbol.")

            # The email validation/RFC debacle is a vortex of endless
            # despair. There have been erratas for the erratas to "fix"
            # the email address issues but it's still very much a source of
            # debate. It's actually gotten to a point where most interwebz
            # people claim that validating email addresses more than the
            # bare minimum is only harmful. I tend to agree with them because
            # each email server implementation follows their own set of rules.
            # This means NO MATTER WHAT WE DO, we're bound to still allow an
            # "invalid" email address depending on the email server being
            # used. It's better to be false-positive than false-negative here.
            # The only guaranteed way to "validate" an email address is to send
            # a test email to the given address.
            local_part = value[:right_most_atsign]
            if not local_part:
                raise ValueError("Missing local part of email string (part before the '@').")

            domain_part = value[right_most_atsign:]
            if domain_part == '@':
                raise ValueError("Missing domain part of email string (part after the '@').")


class Exact(ValidatorBase):
    def __init__(self, value):
        self.value = value

    def __call__(self, value):
        if value != self.value:
            raise ValueError(f"Should be {self.value!r}")


class IpAddress(ValidatorBase):
    def __call__(self, value):
        try:
            ipaddress.ip_address(value)
        except ValueError:
            raise ValueError('Not a valid IP address')


class Netmask(ValidatorBase):
    def __init__(self, ipv4=True, ipv6=True, prefix_length=True):
        self.ipv4 = ipv4
        self.ipv6 = ipv6
        self.prefix_length = prefix_length

    def __call__(self, value):
        if not self.prefix_length and value.isdigit():
            raise ValueError('Please specify expanded netmask i.e 255.255.255.128.')

        ip = '1.1.1.1'
        if self.ipv4 and self.ipv6 and value.isdigit():
            if int(value) > 32:
                ip = '2001:db8::'
        elif self.ipv6 and not self.ipv4:
            # ipaddress module does not currently support ipv6 expanded netmasks
            # TODO: Convert expanded netmasks to prefix lengths for ipv6 till ipaddress adds support
            ip = '2001:db8::'

        try:
            ipaddress.ip_network(f'{ip}/{value}', strict=False)
        except ValueError:
            raise ValueError('Not a valid netmask')


class Time(ValidatorBase):
    def __call__(self, value):
        try:
            hours, minutes = value.split(':')
        except ValueError:
            raise ValueError('Time should be in 24 hour format like "18:00"')
        else:
            try:
                time(int(hours), int(minutes))
            except TypeError:
                raise ValueError('Time should be in 24 hour format like "18:00"')


class Match(ValidatorBase):
    def __init__(self, pattern, flags=0, explanation=None):
        self.pattern = pattern
        self.flags = flags
        self.explanation = explanation

        self.regex = re.compile(pattern, flags)

    def __call__(self, value):
        if value is not None and not self.regex.match(value):
            raise ValueError(self.explanation or f"Value does not match {self.pattern!r} pattern")

    def __deepcopy__(self, memo):
        return Match(self.pattern, self.flags, self.explanation)


class NotMatch(ValidatorBase):
    def __init__(self, pattern, flags=0, explanation=None):
        self.pattern = pattern
        self.flags = flags
        self.explanation = explanation
        self.regex = re.compile(pattern, flags)

    def __call__(self, value):
        if value is not None and self.regex.match(value):
            raise ValueError(self.explanation or f"Value matches {self.pattern!r} pattern")

    def __deepcopy__(self, memo):
        return NotMatch(self.pattern, self.flags, self.explanation)


class Hostname(Match):
    def __init__(self, explanation=None):
        super().__init__(
            r'^[a-z\.\-0-9]*[a-z0-9]$',
            flags=re.IGNORECASE,
            explanation=explanation
        )


class Or(ValidatorBase):
    def __init__(self, *validators):
        self.validators = validators

    def __call__(self, value):
        errors = []

        for validator in self.validators:
            try:
                validator(value)
            except ValueError as e:
                errors.append(str(e))
            else:
                return

        raise ValueError(" or ".join(errors))


class Range(ValidatorBase):
    def __init__(self, min_=None, max_=None, exclude=None):
        self.min = min_
        self.max = max_
        self.exclude = exclude or []

    def __call__(self, value):
        if value is None:
            return
        if isinstance(value, str):
            value = len(value)
        if value in self.exclude:
            raise ValueError(
                f'{value} is a reserved for internal use. Please select another value.'
            )

        error = {
            (True, True): f"between {self.min} and {self.max}",
            (False, True): f"less or equal than {self.max}",
            (True, False): f"greater or equal than {self.min}",
            (False, False): "",
        }[self.min is not None, self.max is not None]

        if self.min is not None and value < self.min:
            raise ValueError(f"Should be {error}")

        if self.max is not None and value > self.max:
            raise ValueError(f"Should be {error}")


class Port(Range):
    ''' Example usage with exclude:
    validators=[Port(exclude=[NFS_RDMA_DEFAULT_PORT])]
    '''
    def __init__(self, exclude=None):
        super().__init__(min_=1, max_=65535, exclude=exclude)


class QueryFilters(ValidatorBase):
    def __call__(self, value: list) -> list:
        validate_filters(value)
        return value


class QueryOptions(ValidatorBase):
    def __call__(self, value):
        validate_options(value)


class Unique(ValidatorBase):
    def __call__(self, value):
        for item in value:
            if value.count(item) > 1:
                raise ValueError(f"Duplicate values are not allowed: {item!r}")


class IpInUse(ValidatorBase):
    def __init__(self, middleware, exclude=None):
        self.middleware = middleware
        self.exclude = exclude or []

    def __call__(self, ip):
        IpAddress()(ip)

        # ip is valid
        if ip not in self.exclude:
            ips = [d['address'] for d in self.middleware.call_sync('interface.ip_in_use')]
            if ip in ips:
                raise ValueError(
                    f'{ip} is already being used by the system. Please select another IP'
                )


class MACAddr(ValidatorBase):

    SEPARATORS = [':', '-']

    def __init__(self, separator=None):
        if separator:
            assert separator in self.SEPARATORS
        self.separator = separator

    def __call__(self, value):
        if not RE_MAC_ADDRESS.match(value.lower()) or (
            self.separator and (
                self.separator not in value or ({self.separator} ^ set(self.SEPARATORS)).pop() in value.lower()
            )
        ):
            raise ValueError('Please provide a valid MAC address')


class ReplicationSnapshotNamingSchema(ValidatorBase):
    def __call__(self, value):
        validate_snapshot_naming_schema(value)


class UUID(ValidatorBase):
    def __call__(self, value):
        if value is None:
            return

        try:
            uuid.UUID(value, version=4)
        except ValueError as e:
            raise ValueError(f'Invalid UUID: {e}')


class PasswordComplexity(ValidatorBase):
    def __init__(self, required_types, required_cnt=None):
        self.required_types = required_types
        self.required_cnt = required_cnt

    def __call__(self, value):
        cnt = 0
        reqs = []
        errstr = ''

        if value and self.required_types:
            if 'ASCII_LOWER' in self.required_types:
                reqs.append('lowercase character')
                if not any(c in ascii_lowercase for c in value):
                    if self.required_cnt is None:
                        errstr += 'Must contain at least one lowercase character. '
                else:
                    cnt += 1

            if 'ASCII_UPPER' in self.required_types:
                reqs.append('uppercase character')
                if not any(c in ascii_uppercase for c in value):
                    if self.required_cnt is None:
                        errstr += 'Must contain at least one uppercase character. '
                else:
                    cnt += 1

            if 'DIGIT' in self.required_types:
                reqs.append('digits 0-9')
                if not any(c in digits for c in value):
                    if self.required_cnt is None:
                        errstr += 'Must contain at least one numeric digit (0-9). '
                else:
                    cnt += 1

            if 'SPECIAL' in self.required_types:
                reqs.append('special characters (!, $, #, %, etc.)')
                if not any(c in punctuation for c in value):
                    if self.required_cnt is None:
                        errstr += 'Must contain at least one special character (!, $, #, %, etc.). '
                else:
                    cnt += 1

        if self.required_cnt and self.required_cnt > cnt:
            raise ValueError(
                f'Must contain at least {self.required_cnt} of the following categories: {", ".join(reqs)}'
            )

        if errstr:
            raise ValueError(errstr)


def validate_schema(schema, data, additional_attrs=False, dict_kwargs=None):
    from middlewared.schema import Dict, Error
    from middlewared.service import ValidationErrors
    verrors = ValidationErrors()
    dict_kwargs = dict_kwargs or {}

    schema = Dict("attributes", *schema, additional_attrs=additional_attrs, **dict_kwargs)

    try:
        schema.clean(data)
    except Error as e:
        verrors.add(e.attribute, e.errmsg, e.errno)
    except ValidationErrors as e:
        verrors.extend(e)
    else:
        try:
            schema.validate(data)
        except ValidationErrors as e:
            verrors.extend(e)

    for verror in verrors.errors:
        if not verror.attribute.startswith("attributes."):
            raise ValueError(f"Got an invalid attribute name: {verror.attribute!r}")

        verror.attribute = verror.attribute[len("attributes."):]

    return verrors


class URL(ValidatorBase):
    def __init__(self, **kwargs):
        kwargs.setdefault("empty", False)
        kwargs.setdefault("scheme", ["http", "https"])

        self.empty = kwargs["empty"]
        self.scheme = kwargs["scheme"]

    def __call__(self, value):
        if self.empty and not value:
            return

        try:
            result = urlparse(value)
        except Exception as e:
            raise ValueError(f'Invalid URL: {e}')

        if not result.scheme:
            raise ValueError('Invalid URL: no scheme specified')

        if self.scheme and result.scheme not in self.scheme:
            raise ValueError(f'Invalid URL: invalid scheme: {result.scheme}')

        if not result.netloc:
            raise ValueError('Invalid URL: no netloc specified')


def check_path_resides_within_volume_sync(verrors, schema_name, path, vol_names):
    """
    This provides basic validation of whether a given `path` is allowed to
    be exposed to end-users.

    `verrors` - ValidationErrors created by calling function

    `schema_name` - schema name to use in validation error message

    `path` - path to validate

    `vol_names` - list of expected pool names

    It checks the following:
    * path is within /mnt
    * path is located within one of the specified `vol_names`
    * path is not explicitly a `.zfs` or `.zfs/snapshot` directory
    """
    if path_location(path).name == 'EXTERNAL':
        # There are some fields where we allow external paths
        verrors.add(schema_name, "Path is external to TrueNAS.")
        return

    try:
        inode = os.stat(path).st_ino
    except FileNotFoundError:
        inode = None

    rp = Path(os.path.realpath(path))

    vol_paths = [os.path.join("/mnt", vol_name) for vol_name in vol_names]
    if not path.startswith("/mnt/") or not any(
        os.path.commonpath([parent]) == os.path.commonpath([parent, rp]) for parent in vol_paths
    ):
        verrors.add(schema_name, "The path must reside within a pool mount point")

    if inode in (ZFSCTL.INO_ROOT.value, ZFSCTL.INO_SNAPDIR.value):
        verrors.add(schema_name,
                    "The ZFS control directory (.zfs) and snapshot directory (.zfs/snapshot) "
                    "are not permitted paths. If a snapshot within this directory must "
                    "be accessed through the path-based API, then it should be called "
                    "directly, e.g. '/mnt/dozer/.zfs/snapshot/mysnap'.")
