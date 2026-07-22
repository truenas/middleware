#!/usr/bin/env python3

import os
import sys
from pytest_dependency import depends

sys.path.append(os.getcwd())

from middlewared.test.integration.assets.nfs import nfs_share
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.snapshot_task import snapshot_task
from middlewared.test.integration.utils import call, client


PARENT_DATASET = 'test_parent'
CHILD_DATASET = f'{PARENT_DATASET}/child_dataset'


def test_attachment_with_child_path(request):
    with dataset(PARENT_DATASET) as parent_dataset:
        parent_path = f'/mnt/{parent_dataset}'
        assert call('pool.dataset.attachments_with_path', parent_path) == []

        with nfs_share(parent_dataset):
            attachments = call('pool.dataset.attachments_with_path', parent_path)
            assert len(attachments) > 0, attachments
            assert attachments[0]['type'] == 'NFS Share', attachments

            with dataset(CHILD_DATASET) as child_dataset:
                child_path = f'/mnt/{child_dataset}'
                attachments = call('pool.dataset.attachments_with_path', child_path)
                assert len(attachments) == 0, attachments

                attachments = call('pool.dataset.attachments_with_path', child_path, True)
                assert len(attachments) == 1, attachments
                assert attachments[0]['type'] == 'NFS Share', attachments


def test_attachment_name_for_snapshot_task():
    """A periodic snapshot task is reported by `attachments_with_path`.

    Unlike share delegates (which return dicts), `pool.snapshottask` returns type-safe models, so this
    exercises the `getattr` (non-dict) branch of the base delegate's `get_attachment_name`.
    """
    with dataset(PARENT_DATASET) as parent_dataset:
        parent_path = f'/mnt/{parent_dataset}'
        with snapshot_task({
            "dataset": parent_dataset,
            "recursive": False,
            "lifetime_value": 1,
            "lifetime_unit": "WEEK",
            "naming_schema": "auto-%Y%m%d.%H%M%S-1w",
            "schedule": {},
            "enabled": True,
        }):
            attachments = call('pool.dataset.attachments_with_path', parent_path)
            snapshot_tasks = [a for a in attachments if a['type'] == 'Snapshot Task']
            assert snapshot_tasks == [{'type': 'Snapshot Task', 'service': None, 'attachments': [parent_dataset]}], (
                attachments
            )
