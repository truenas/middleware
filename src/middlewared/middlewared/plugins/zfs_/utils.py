import enum
import os

from truenas_os_pyutils.mount import statmount

from middlewared.plugins.audit.utils import AUDIT_DEFAULT_FILL_CRITICAL, AUDIT_DEFAULT_FILL_WARNING
from middlewared.service_exception import CallError
from middlewared.utils.boot.pool import BOOT_POOL_NAME_VALID
from middlewared.utils.path import is_child

__all__ = [
    "path_to_dataset_impl",
    "paths_to_datasets_impl",
    "zvol_name_to_path",
    "zvol_path_to_name",
]

LEGACY_USERPROP_PREFIX = 'org.freenas'
USERPROP_PREFIX = 'org.truenas'


class TNUserProp(enum.Enum):
    DESCRIPTION = f'{LEGACY_USERPROP_PREFIX}:description'
    QUOTA_WARN = f'{LEGACY_USERPROP_PREFIX}:quota_warning'
    QUOTA_CRIT = f'{LEGACY_USERPROP_PREFIX}:quota_critical'
    REFQUOTA_WARN = f'{LEGACY_USERPROP_PREFIX}:refquota_warning'
    REFQUOTA_CRIT = f'{LEGACY_USERPROP_PREFIX}:refquota_critical'
    MANAGED_BY = f'{USERPROP_PREFIX}:managedby'

    def default(self):
        # NOTE: DONT CHANGE THESE VALUES WITHOUT CHANGING
        # THE UX! The UX has hard-coded these values on
        # a form and so changing them here will cause
        # confusion for end-user.
        match self:
            case TNUserProp.QUOTA_WARN:
                return 80
            case TNUserProp.QUOTA_CRIT:
                return 95
            case TNUserProp.REFQUOTA_WARN:
                return 80
            case TNUserProp.REFQUOTA_CRIT:
                return 95
            case _:
                raise ValueError(f'{self.value}: no default value is set')

    def quotas():
        return [(a.value, a.default()) for a in [
            TNUserProp.QUOTA_WARN,
            TNUserProp.QUOTA_CRIT,
            TNUserProp.REFQUOTA_WARN,
            TNUserProp.REFQUOTA_CRIT
        ]]

    def audit_quotas():
        # Same shape as quotas(), but the audit dataset defaults to its own
        # warning/critical thresholds rather than the general-purpose values
        # from default(). Only a default: the on-disk user properties (which
        # can be changed by the user) take precedence when present.
        return [
            (TNUserProp.QUOTA_WARN.value, AUDIT_DEFAULT_FILL_WARNING),
            (TNUserProp.QUOTA_CRIT.value, AUDIT_DEFAULT_FILL_CRITICAL),
            (TNUserProp.REFQUOTA_WARN.value, AUDIT_DEFAULT_FILL_WARNING),
            (TNUserProp.REFQUOTA_CRIT.value, AUDIT_DEFAULT_FILL_CRITICAL),
        ]

    def values():
        return [a.value for a in TNUserProp]


def zvol_name_to_path(name):
    return os.path.join("/dev/zvol", name.replace(" ", "+"))


def zvol_path_to_name(path):
    if not path.startswith("/dev/zvol/"):
        raise ValueError(f"Invalid zvol path: {path!r}")

    return path[len("/dev/zvol/"):].replace("+", " ")


def paths_to_datasets_impl(
    paths: list[str],
) -> dict[str, str | None]:
    """
    Convert `paths` to a dictionary of ZFS dataset names. This
    performs lookup through mountinfo.

    Anticipated error conditions are that paths are not
    on ZFS or if the boot pool underlies the path. In
    addition to this, all the normal exceptions that
    can be raised by a failed call to os.stat() are
    possible. If any exception occurs, the dataset name
    will be set to None in the dictionary.
    """
    rv = dict()

    for path in paths:
        try:
            rv[path] = path_to_dataset_impl(path)
        except Exception:
            rv[path] = None

    return rv


def path_to_dataset_impl(path: str) -> str:
    """
    Convert `path` to a ZFS dataset name. This
    performs lookup through mountinfo.

    Anticipated error conditions are that path is not
    on ZFS or if the boot pool underlies the path. In
    addition to this, all the normal exceptions that
    can be raised by a failed call to os.stat() are
    possible.
    """
    sm = statmount(path=path, as_dict=False)
    if sm.fs_type != 'zfs':
        raise CallError(f'{path}: path is not a ZFS filesystem')

    ds_name = sm.sb_source
    for bp_name in BOOT_POOL_NAME_VALID:
        if is_child(ds_name, bp_name):
            raise CallError(f'{path}: path is on boot pool')

    return ds_name
