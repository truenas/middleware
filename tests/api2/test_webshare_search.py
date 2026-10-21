import pytest

from middlewared.service_exception import ValidationError
from middlewared.test.integration.assets.entitlements import entitled
from middlewared.test.integration.utils import call


@pytest.fixture
def search():
    search = call("webshare.config")["search"]
    try:
        yield search
    finally:
        with entitled("TRUESEARCH"):
            call("webshare.update", {"search": search})


def test_enabling_search_is_rejected_without_truesearch_entitlement(search):
    with entitled("TRUESEARCH", False):
        with pytest.raises(ValidationError) as ve:
            call("webshare.update", {"search": True})

    assert ve.value.attribute == "search"
    assert ve.value.errmsg.startswith("Share indexing service is not available.")
    assert call("webshare.config")["search"] == search


def test_enabling_search_is_allowed_with_truesearch_entitlement(search):
    with entitled("TRUESEARCH"):
        assert call("webshare.update", {"search": True})["search"] is True

    assert call("webshare.config")["search"] is True
