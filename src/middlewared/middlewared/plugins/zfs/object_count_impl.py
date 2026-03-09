import logging
import typing

import truenas_pylibzfs

from .exceptions import ZFSPathNotFoundException
from .utils import open_resource

__all__ = ('estimate_object_count_impl',)

logger = logging.getLogger(__name__)


def estimate_object_count_impl(tls: typing.Any, dataset_name: str) -> int:
    """Estimate total objects (files + dirs) in a dataset via ZFS quota accounting.

    Uses GROUPOBJ_USED quota type which sums object counts per group across
    the dataset. This is a fast in-memory ZFS operation — no filesystem walk.

    Returns 0 on any error (caller treats 0 as "unknown").
    """
    try:
        rsrc = open_resource(tls, dataset_name)
    except ZFSPathNotFoundException:
        return 0
    except Exception:
        logger.warning('%s: failed to open ZFS resource for object count estimate', dataset_name, exc_info=True)
        return 0

    if rsrc.type != truenas_pylibzfs.ZFSType.ZFS_TYPE_FILESYSTEM:
        return 0

    cnt = 0

    def _cb(quota: typing.Any, state: typing.Any) -> bool:
        nonlocal cnt
        cnt += quota.value
        return True

    # GROUPOBJ_USED is used instead of USEROBJ_USED because there are typically
    # far fewer distinct owning gids than owning uids across a dataset, so the
    # callback is invoked fewer times while still yielding the same total count.
    try:
        rsrc.iter_userspace(
            quota_type=truenas_pylibzfs.ZFSUserQuota.GROUPOBJ_USED,
            callback=_cb,
            state=None,
        )
    except Exception:
        logger.warning('%s: failed to estimate object count', dataset_name, exc_info=True)
        return 0

    return cnt
