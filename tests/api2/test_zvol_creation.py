from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call

_1GiB = 1073741824
BASE_NAME = "test_create_zvol"
BASE_ARGS = {"type": "VOLUME", "volsize": _1GiB}


def query_zvol(zvol):
    result = call(
        "zfs.resource.query",
        {"paths": [zvol], "properties": ["refreservation", "volsize"]},
    )
    assert result and len(result) == 1
    return (
        result[0]["properties"]["refreservation"]["value"],
        result[0]["properties"]["volsize"]["value"],
    )


def test_create_thick_provisioned_zvol_sparse_false():
    # sparse is explicitly provided as false so
    # thick provisioned zvol should be created
    args = BASE_ARGS | {"sparse": False}
    with dataset(f"{BASE_NAME}1", args) as ds:
        rr, vs = query_zvol(ds)
        assert rr == _1GiB
        assert vs == _1GiB


def test_create_thick_provisioned_zvol_sparse_not_provided():
    # sparse not explicitly provided so API should default to thick
    with dataset(f"{BASE_NAME}2", BASE_ARGS) as ds:
        rr, vs = query_zvol(ds)
        assert rr == _1GiB
        assert vs == _1GiB


def test_create_thin_provisioned_zvol_sparse_true():
    # sparse explicitly provided as true so
    # thin provisoned zvol should be created
    args = BASE_ARGS | {"sparse": True}
    with dataset(f"{BASE_NAME}3", args) as ds:
        rr, vs = query_zvol(ds)
        assert rr == 0
        assert vs == _1GiB


def test_create_thin_provisioned_zvol_refreservation_explicit_zero():
    # refreservation explicitly provided and given as 0
    # which means thin provisioned
    args = BASE_ARGS | {"refreservation": 0}
    with dataset(f"{BASE_NAME}4", args) as ds:
        rr, vs = query_zvol(ds)
        assert rr == 0
        assert vs == _1GiB


def test_create_thick_provisioned_zvol_refreservation_explicit_value():
    # refreservation explicitly provided by is half of the
    # volume size so thick provisioned zvol is created
    args = BASE_ARGS | {"refreservation": _1GiB // 2}
    with dataset(f"{BASE_NAME}5", args) as ds:
        rr, vs = query_zvol(ds)
        assert rr == _1GiB // 2
        assert vs == _1GiB
