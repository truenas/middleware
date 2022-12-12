import contextlib
import urllib.parse
from time import sleep

from functions import DELETE, GET, POST, PUT, wait_on_job


@contextlib.contextmanager
def dataset(pool_name, dataset_name, options=None, **kwargs):

    dataset = f"{pool_name}/{dataset_name}"
    payload = { 'name': dataset, **(options or {}) }

    results = POST("/pool/dataset/", payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    dataset_config = results.json()

    if 'acl' in kwargs or 'mode' in kwargs:
        if 'acl' in kwargs:
            result = POST("/filesystem/setacl/", {'path': f"/mnt/{dataset}", "dacl": kwargs['acl']})
        else:
            result = POST("/filesystem/setperm/", {'path': f"/mnt/{dataset}", "mode": kwargs['mode'] or "777"})

        assert result.status_code == 200, result.text
        job_status = wait_on_job(result.json(), 180)
        assert job_status["state"] == "SUCCESS", str(job_status["results"])

    try:
        yield dataset_config
    finally:
        if 'delete_delay' in kwargs:
            sleep(kwargs['delete_delay'])
        results = DELETE(f"/pool/dataset/id/{urllib.parse.quote(dataset, '')}/", {'recursive' : True} )
        assert results.status_code == 200, results.text
