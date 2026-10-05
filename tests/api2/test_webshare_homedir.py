import pytest

from middlewared.test.integration.assets.entitlements import entitled
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.webshare import webshare_share
from middlewared.test.integration.utils import call


@pytest.fixture(scope="module", autouse=True)
def webshare_entitled():
    # Creating a share and enabling an existing one are gated by the WEBSHARE entitlement,
    # which an unlicensed test runner does not have.
    with entitled("WEBSHARE"):
        yield


def test_webshare_is_home_base_field():
    """Test that webshare shares support the is_home_base field"""
    with dataset("webshare_is_home_base_test_1") as ds1:
        with dataset("webshare_is_home_base_test_2") as ds2:
            with webshare_share(f"/mnt/{ds1}", "Share1", {"is_home_base": False}) as share1:
                assert share1["is_home_base"] is False

                with webshare_share(f"/mnt/{ds2}", "Share2", {"is_home_base": True}) as share2:
                    assert share2["is_home_base"] is True


def test_webshare_is_home_base_only_one_allowed():
    """Test that only one share can have is_home_base enabled"""
    with dataset("webshare_is_home_base_validation_1") as ds1:
        with dataset("webshare_is_home_base_validation_2") as ds2:
            with webshare_share(f"/mnt/{ds1}", "HomeShare", {"is_home_base": True}):
                with pytest.raises(Exception) as exc_info:
                    call(
                        "sharing.webshare.create",
                        {
                            "name": "AnotherHomeShare",
                            "path": f"/mnt/{ds2}",
                            "is_home_base": True,
                        },
                    )

                assert "Only one share can be configured as home directory base" in str(exc_info.value)

                with webshare_share(f"/mnt/{ds2}", "RegularShare", {"is_home_base": False}) as share2:
                    assert share2["is_home_base"] is False

                    with pytest.raises(Exception) as exc_info:
                        call(
                            "sharing.webshare.update",
                            share2["id"],
                            {
                                "is_home_base": True,
                            },
                        )

                    assert "Only one share can be configured as home directory base" in str(exc_info.value)


def test_webshare_is_home_base_update_to_true():
    """Test updating a share to enable is_home_base when no other share has it"""
    with dataset("webshare_is_home_base_update") as ds:
        with webshare_share(f"/mnt/{ds}", "TestShare", {"is_home_base": False}) as share:
            assert share["is_home_base"] is False

            updated_share = call(
                "sharing.webshare.update",
                share["id"],
                {
                    "is_home_base": True,
                },
            )

            assert updated_share["is_home_base"] is True

            updated_share = call(
                "sharing.webshare.update",
                share["id"],
                {
                    "is_home_base": False,
                },
            )

            assert updated_share["is_home_base"] is False
