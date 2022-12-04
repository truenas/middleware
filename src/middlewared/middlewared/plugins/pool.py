import asyncio
import contextlib
import enum
import errno
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
import os
import re
import secrets
import shutil
import uuid

from collections import defaultdict
from io import BytesIO

from middlewared.alert.base import AlertCategory, AlertClass, AlertLevel, SimpleOneShotAlertClass
from middlewared.schema import (
    accepts, Attribute, Bool, Dict, EnumMixin, Int, List, Patch, Str, UnixPerm, Any,
    Ref, returns, OROperator, NOT_PROVIDED,
)
from middlewared.plugins.pool_.utils import dataset_can_be_mounted
from middlewared.service import (
    item_method, job, private, CallError, CRUDService, ValidationErrors, periodic
)
from middlewared.utils import filter_list
from middlewared.utils.path import is_child
from middlewared.utils.size import MB
from middlewared.validators import Range

logger = logging.getLogger(__name__)


class ZfsDeadmanAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = "Device Is Causing Slow I/O on Pool"
    text = "Device %(vdev)s is causing slow I/O on pool %(pool)s."

    expires_after = timedelta(hours=4)

    hardware = True


class ZFSKeyFormat(enum.Enum):
    HEX = 'HEX'
    PASSPHRASE = 'PASSPHRASE'
    RAW = 'RAW'


def _none(x):
    if x in (0, None):
        return 'none'
    return x


class PoolDatasetService(CRUDService):

    attachment_delegates = []
    dataset_store = 'storage.encrypteddataset'

    class Config:
        datastore_primary_key_type = 'string'
        namespace = 'pool.dataset'
        event_send = False
        cli_namespace = 'storage.dataset'

    @item_method
    @accepts(Str('id'))
    @returns()
    async def promote(self, id):
        """
        Promote the cloned dataset `id`.
        """
        dataset = await self.middleware.call('zfs.dataset.query', [('id', '=', id)])
        if not dataset:
            raise CallError(f'Dataset "{id}" does not exist.', errno.ENOENT)
        if not dataset[0]['properties']['origin']['value']:
            raise CallError('Only cloned datasets can be promoted.', errno.EBADMSG)
        return await self.middleware.call('zfs.dataset.promote', id)
