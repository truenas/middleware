import contextlib
import urllib.parse
from functions import POST, SSH_TEST, DELETE, wait_on_job
from time import sleep

@contextlib.contextmanager
def create_dataset(dataset, options=None, acl=None, mode=None):
    perm_job = None

    result = POST("/pool/dataset/", {"name": dataset, **(options or {})})
    assert result.status_code == 200, result.text

    if mode is not None:
        perm_job = POST("/filesystem/setperm/", {'path': f"/mnt/{dataset}", "mode": mode})
    elif acl is not None:
        perm_job = POST("/filesystem/setacl/", {'path': f"/mnt/{dataset}", "dacl": acl})

    if perm_job:
        assert perm_job.status_code == 200, result.text
        job_status = wait_on_job(perm_job.json(), 180)
        assert job_status["state"] == "SUCCESS", str(job_status["results"])

    try:
        yield dataset
    finally:
        # dataset may be busy
        sleep(5)
        result = DELETE(f"/pool/dataset/id/{urllib.parse.quote(dataset, '')}/",
                        {'recursive': True})
        assert result.status_code == 200, result.text
