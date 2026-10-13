import enum
import os
import re
from typing import NamedTuple

from middlewared.plugins.system_dataset.utils import SYSDATASET_PATH

RE_DOMAIN_WILDCARD = re.compile(r"\*|\?|\[|\]")


class NFSPath(NamedTuple):
    path: str
    mode: int
    is_dir: bool
    uid: int | str
    gid: int | str


class NFSServicePathInfo(NFSPath, enum.Enum):
    # nfs conf sections that use STATEDIR: exportd, mountd, statd
    STATEDIR = NFSPath(os.path.join(SYSDATASET_PATH, "nfs"), 0o755, True, 0, 0)
    CLDDIR = NFSPath(os.path.join(SYSDATASET_PATH, "nfs", "nfsdcld"), 0o700, True, 0, 0)
    CLDTRKDIR = NFSPath(os.path.join(SYSDATASET_PATH, "nfs", "nfsdcltrack"), 0o700, True, 0, 0)
    # name_to_id_conversion resolves these names in setup_directories
    SMDIR = NFSPath(os.path.join(SYSDATASET_PATH, "nfs", "sm"), 0o755, True, "statd", "nogroup")
    SMBAKDIR = NFSPath(os.path.join(SYSDATASET_PATH, "nfs", "sm.bak"), 0o755, True, "statd", "nogroup")
    V4RECOVERYDIR = NFSPath(os.path.join(SYSDATASET_PATH, "nfs", "v4recovery"), 0o755, True, 0, 0)


class NFSProtocol(str, enum.Enum):
    NFSv3 = "NFSV3"
    NFSv4 = "NFSV4"


def get_domain(hostname: str) -> str | None:
    """
    return the 'domain' part of the hostname
    e.g. gruff.billy.goat will return 'billy.goat'
    and  gruffbillygoat will return None
    """
    lst = hostname.split(".", 1)
    if len(lst) > 1:
        return lst[1]
    return None


def leftmost_has_wildcards(hostname: str) -> bool:
    """
    A bool that returns True if the left most level contains wildcards
    """
    return bool(RE_DOMAIN_WILDCARD.search(hostname.split(".")[0]))


def get_wildcard_domain(hostname: str) -> str | None:
    """
    If the left most level of the supplied hostname contains valid wildcard characters
       and there is more than one level in the name,
    then return the domain part.
    e.g. asdf-* will return None
         asdf-*.example.com will return example.com
         fred.example.com will return None
    """
    if leftmost_has_wildcards(hostname):
        return get_domain(hostname)
    return None
