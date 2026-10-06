from types import SimpleNamespace

import pytest

from middlewared.plugins.pool_.dataset_query_utils import normalize_zfs_asdict_result, user_property_names_to_be_renamed
from middlewared.plugins.zfs_.utils import TNUserProp


def handle(name="tank/incus/vol"):
    return SimpleNamespace(name=name, type=SimpleNamespace(name="ZFS_TYPE_VOLUME"), pool_name=name.split("/")[0])


def normalized(user_properties, **kwargs):
    return normalize_zfs_asdict_result({"properties": {}, "user_properties": user_properties}, handle(), **kwargs)


def test_internal_user_properties_are_top_level_fields_not_user_properties():
    result = normalized({
        TNUserProp.MANAGED_BY.value: "incus.truenas",
        TNUserProp.DESCRIPTION.value: "Managed by Incus.TrueNAS",
        "incus:content_type": "filesystem",
    })

    assert result["managedby"]["parsed"] == "incus.truenas"
    assert result["comments"]["parsed"] == "Managed by Incus.TrueNAS"
    # `pool.dataset.update` removes every key of `user_properties` that is missing from a `user_properties` update,
    # so internal properties showing up here (under their API names, which ZFS does not know) break such updates.
    assert list(result["user_properties"]) == ["incus:content_type"]


@pytest.mark.parametrize("user_prop,api_name", [
    (TNUserProp.DESCRIPTION, "comments"),
    (TNUserProp.QUOTA_WARN, "quota_warning"),
    (TNUserProp.QUOTA_CRIT, "quota_critical"),
    (TNUserProp.REFQUOTA_WARN, "refquota_warning"),
    (TNUserProp.REFQUOTA_CRIT, "refquota_critical"),
    (TNUserProp.MANAGED_BY, "managedby"),
])
def test_every_renamed_internal_property_is_lifted(user_prop, api_name):
    result = normalized({user_prop.value: "x", "a:b": "c"})

    assert result[api_name]["value"] == "x"
    assert api_name not in result["user_properties"]
    assert user_prop.value not in result["user_properties"]
    assert list(result["user_properties"]) == ["a:b"]


def test_all_renamed_names_are_covered():
    # If a new internal property gets a rename, it has to be exposed as a top-level field as well.
    assert set(user_property_names_to_be_renamed().values()) == {
        "comments", "quota_warning", "quota_critical", "refquota_warning", "refquota_critical", "managedby",
    }


def test_user_properties_without_internal_ones_are_untouched():
    result = normalized({"a:b": "c", "d:e": "f"})

    assert list(result["user_properties"]) == ["a:b", "d:e"]
    assert not {"comments", "managedby", "quota_warning"} & result.keys()


def test_no_user_properties():
    assert normalized(None)["user_properties"] == {}
    assert "user_properties" not in normalized({"a:b": "c"}, include_user_properties=False)
