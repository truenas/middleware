import ipaddress
import os
import re
from pathlib import Path

from middlewared.utils import filters
from middlewared.utils.filesystem.constants import ZFSCTL
from middlewared.utils.path import path_location


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


class IpAddress(ValidatorBase):
    def __call__(self, value):
        try:
            ipaddress.ip_address(value)
        except ValueError:
            raise ValueError('Not a valid IP address')


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
            (False, True): f"less than or equal to {self.max}",
            (True, False): f"greater than or equal to {self.min}",
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


def check_path_resides_within_volume_sync(verrors, schema_name, path, vol_names, must_be_dir=False):
    """
    This provides basic validation of whether a given `path` is allowed to
    be exposed to end-users.

    `verrors` - ValidationErrors created by calling function

    `schema_name` - schema name to use in validation error message

    `path` - path to validate

    `vol_names` - list of expected pool names

    `must_be_dir` - optional check for directory

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

    if must_be_dir and not rp.is_dir():
        verrors.add(schema_name, "The path must be a directory")

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
