import pytest

from middlewared.test.integration.assets.cloud_sync import local_ftp_task
from middlewared.test.integration.assets.pool import dataset, pool
from middlewared.test.integration.utils import call, ssh

pytestmark = pytest.mark.zfs


@pytest.fixture(scope="module")
def cloud_sync_fixture():
    with dataset("test_pool_dataset_details") as test_ds:
        with dataset("test_pool_dataset_details_other") as other_ds:
            with local_ftp_task({
                "path": f"/mnt/{pool}",
            }) as task:
                ssh(f"mkdir -p /mnt/{test_ds}/subdir")
                ssh(f"mkdir -p /mnt/{other_ds}/subdir")
                yield test_ds, other_ds, task


@pytest.mark.parametrize("path,count", [
    # A task that backs up the parent dataset backs up the child dataset too
    (lambda test_ds, other_ds: f"/mnt/{pool}", 1),
    # A task that backs up the dataself itself
    (lambda test_ds, other_ds: f"/mnt/{test_ds}", 1),
    # A task that backs up only the part of the dataset should not count
    (lambda test_ds, other_ds: f"/mnt/{test_ds}/subdir", 0),
    # Unrelated datasets should not count too
    (lambda test_ds, other_ds: f"/mnt/{other_ds}", 0),
    (lambda test_ds, other_ds: f"/mnt/{other_ds}/subdir", 0),
])
def test_cloud_sync(cloud_sync_fixture, path, count):
    test_ds, other_ds, task = cloud_sync_fixture
    call("cloudsync.update", task["id"], {"path": path(test_ds, other_ds)})

    result = call("pool.dataset.details")
    details = [
        ds
        for ds in result
        if ds["name"] == test_ds
    ][0]
    assert details["cloudsync_tasks_count"] == count
