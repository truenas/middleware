#!/usr/bin/env python3

import os
import pytest
import sys
from pytest_dependency import depends

sys.path.append(os.getcwd())

from middlewared.test.integration.assets.nfs import nfs_share
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, client


PARENT_DATASET = 'test_parent'
CHILD_DATASET = f'{PARENT_DATASET}/child_dataset'
pytestmark = pytest.mark.zfs


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
