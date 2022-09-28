import time
import pytest
from functions import POST, GET, PUT, wait_on_job
from pytest_dependency import depends
from auto_config import dev_test, pool_name
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skipping for test development testing')


@pytest.fixture(scope='module')
def reporing_data():
    return {}


def test_reporting_still_working_after_the_system_dataset_changes(request, reporing_data):
    depends(request, ["pool_04"], scope="session")

    pool_disk = [POST('/disk/get_unused/').json()[0]['name']]
    payload = {
        "name": 'second_pool',
        "encryption": False,
        "topology": {
            "data": [
                {"type": "STRIPE", "disks": pool_disk}
            ],
        },
        "allow_duplicate_serials": True,
    }
    results = POST("/pool/", payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    pool_id = job_status['results']['result']['id']

    results = GET("/systemdataset/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert results.json()['pool'] == pool_name, results.text
    assert results.json()['basename'] == f'{pool_name}/.system', results.text

    results = POST('/reporting/get_data/', {'graphs': [{'name': 'cpu'}]})
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    reporing_data['graph_data_1'] = results.json()[0]
    time.sleep(1)

    results = PUT("/systemdataset/", {'pool': 'second_pool'})
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), int), results.text
    job_status = wait_on_job(results.json(), 120)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    results = GET("/systemdataset/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert results.json()['pool'] == 'second_pool', results.text
    assert results.json()['basename'] == 'second_pool/.system', results.text

    results = POST('/reporting/get_data/', {'graphs': [{'name': 'cpu'}]})
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    reporing_data['graph_data_2'] = results.json()[0]

    assert reporing_data['graph_data_1']['data'][-2] in reporing_data['graph_data_2']['data']
    assert reporing_data['graph_data_1']['data'] != reporing_data['graph_data_2']['data']

    payload = {
        'cascade': True,
        'restart_services': True,
        'destroy': True
    }
    results = POST(f'/pool/id/{pool_id}/export/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 120)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    results = GET("/systemdataset/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert results.json()['pool'] == pool_name, results.text
    assert results.json()['basename'] == f'{pool_name}/.system', results.text
