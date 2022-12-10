import contextlib

from functions import DELETE, GET, POST, PUT, wait_on_job


@contextlib.contextmanager
def dataset(pool_name, dataset_name):

    dataset = f"{pool_name}/{dataset_name}"

    payload = {
        'name': dataset,
    }
    results = POST("/pool/dataset/", payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    dataset_config = results.json()

    try:
        yield dataset_config
    finally:
        dataset_id = dataset_config['id'].replace('/', '%2F')
        results = DELETE(f"/pool/dataset/id/{dataset_id}/", {'recursive' : True} )
        assert results.status_code == 200, results.text
