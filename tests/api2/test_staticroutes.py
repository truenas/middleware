import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.utils import call, ssh

ROUTE = {
    "destination": "127.1.1.1",
    "gateway": "127.0.0.1",
    "description": "Test Route",
}
BAD_ROUTE = {"destination": "fe80:aaaa:bbbb:cccc::1/64", "gateway": ROUTE["gateway"]}


def test_staticroute():
    """
    1. try to create invalid route
    2. create valid route
    3. validate route was added to OS
    4. try to update valid route with invalid data
    5. delete route
    6. validate route was removed from OS
    """
    # try to create bad route
    with pytest.raises(ValidationErrors):
        call("staticroute.create", BAD_ROUTE)

    # now create valid one
    id_ = call("staticroute.create", ROUTE)["id"]

    # validate query
    qry = call("staticroute.query", [["id", "=", id_]], {"get": True})
    assert ROUTE["destination"] in qry["destination"]
    assert ROUTE["gateway"] == qry["gateway"]
    assert ROUTE["description"] == qry["description"]

    # validate route was added to OS
    results = ssh(f"ip route show {ROUTE['destination']}", complete_response=True)
    assert f"{ROUTE['destination']} via {ROUTE['gateway']}" in results["stdout"]

    # update it with bad data
    with pytest.raises(ValidationErrors):
        call("staticroute.update", id_, {"destination": BAD_ROUTE["destination"]})

    # now delete
    assert call("staticroute.delete", id_)
    assert not call("staticroute.query", [["id", "=", id_]])

    # validate route was removed from OS
    results = ssh(
        f"ip route show {ROUTE['destination']}", complete_response=True, check=False
    )
    assert ROUTE["destination"] not in results["stdout"]
