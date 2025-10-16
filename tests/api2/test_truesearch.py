import os
import time

import pytest

from middlewared.test.integration.assets.account import user
from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, host, ssh

USERNAME = 'alex'
PASSWORD = 'password'
SHARE_NAME = 'alex'


@pytest.fixture(scope='module')
def share():
    call('smb.update', {'search_protocols': ['SPOTLIGHT']})

    with dataset('truesearch', data={'share_type': 'SMB'}) as ds:
        ssh(f"touch /mnt/{ds}/mytest.txt")

        with user({
            'username': USERNAME,
            'full_name': 'Alex',
            'group_create': True,
            'password': PASSWORD
        }):
            with smb_share(os.path.join('/mnt', ds), SHARE_NAME):
                # FIXME: Remove this when we fix https://ixsystems.atlassian.net/browse/NAS-137715
                ssh("chmod 777 /run/truesearch/truesearch-es.sock")

                yield {
                    'dataset': ds,
                }


def expect_search_result(expected: list[str]):
    for i in range(10):
        result = ssh(f"mdsearch --debug-stdout -U {USERNAME} --password={PASSWORD} {host().ip} {SHARE_NAME} "
                     "'kMDItemDisplayName==\"*test*\"'", check=False, complete_response=True)
        if sorted(result["stdout"].splitlines()) == sorted(expected):
            break

        time.sleep(5)
    else:
        assert False, (result["returncode"], result["output"])


def test_index_and_search(share):
    expect_search_result(["mytest.txt"])


def test_index_new_dataset(share):
    with dataset('truesearch/nested', data={'share_type': 'SMB'}) as ds:
        ssh(f"touch /mnt/{ds}/anothertest.txt")

        # truesearch.schedule_reconfigure will take 5 seconds
        time.sleep(5)

        expect_search_result(["mytest.txt", "nested/anothertest.txt"])


def test_user_cannot_read_file(share):
    prohibited_dir = f"/mnt/{share['dataset']}/prohibited"
    ssh(f"mkdir {prohibited_dir}")
    ssh(f"touch {prohibited_dir}/prohibitedtest.txt")

    expect_search_result(["mytest.txt", "prohibited/prohibitedtest.txt"])

    call("filesystem.setperm", {"path": prohibited_dir, "mode": "700", "options": {"stripacl": True}}, job=True)

    expect_search_result(["mytest.txt"])
