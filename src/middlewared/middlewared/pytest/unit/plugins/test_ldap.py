from middlewared.utils.directoryservices import ldap_constants as constants
from middlewared.utils.directoryservices import ldap_utils as utils

FREEIPA_SAMPLE_SEARCH_BASE = {
    "base_user": "cn=users,cn=accounts,dc=tn,dc=ixsystems,dc=net",
    "base_group": "cn=groups,cn=accounts,dc=tn,dc=ixsystems,dc=net",
    "base_netgroup": "netgroup cn=ng,cn=compat,dc=tn,dc=ixsystems,dc=net"
}
FREEIPA_SAMPLE_ATTR_MAPS = {
    "passwd": {
        "user_object_class": None,
        "user_name": None,
        "user_uid": None,
        "user_gid": None,
        "user_gecos": None,
        "user_home_directory": None,
        "user_shell": None
    },
    "shadow": {
        "shadow_last_change": None,
        "shadow_min": None,
        "shadow_max": None,
        "shadow_warning": None,
        "shadow_inactive": None,
        "shadow_expire": None
    },
    "group": {
        "group_object_class": None,
        "group_gid": None,
        "group_member": None
    },
    "netgroup": {
        "netgroup_object_class": None,
        "netgroup_member": None,
        "netgroup_triple": None
    }
}

NONE_SAMPLE_SEARCH_BASE = {
    "base_user": None,
    "base_group": None,
    "base_netgroup": None
}


def test__freeipa_schema_conversion():
    # This verifies we're not getting unexpected lines added by having NULL entries
    assert len(utils.attribute_maps_data_to_params(FREEIPA_SAMPLE_ATTR_MAPS)) == 0

    search_bases = utils.search_base_data_to_params(FREEIPA_SAMPLE_SEARCH_BASE)
    assert len(search_bases) == 3
    for key, entry in FREEIPA_SAMPLE_SEARCH_BASE.items():
        match key:
            case "base_user":
                assert f'ldap_user_search_base = {entry}' in search_bases
            case "base_group":
                assert f'ldap_group_search_base = {entry}' in search_bases
            case "base_netgroup":
                assert f'ldap_netgroup_search_base = {entry}' in search_bases


def test__default_search_base():
    assert len(utils.search_base_data_to_params(NONE_SAMPLE_SEARCH_BASE)) == 0


def test__attribute_map_keys_passwd():
    for key in constants.LDAP_PASSWD_MAP_KEYS:
        data = {"passwd": {key: "canary"}}
        results = utils.attribute_maps_data_to_params(data)
        assert len(results) == 1

        match key:
            case constants.ATTR_USER_OBJ:
                assert results[0] == "ldap_user_object_class = canary"
            case constants.ATTR_USER_NAME:
                assert results[0] == "ldap_user_name = canary"
            case constants.ATTR_USER_UID:
                assert results[0] == "ldap_user_uid_number = canary"
            case constants.ATTR_USER_GID:
                assert results[0] == "ldap_user_gid_number = canary"
            case constants.ATTR_USER_GECOS:
                assert results[0] == "ldap_user_gecos = canary"
            case constants.ATTR_USER_HOMEDIR:
                assert results[0] == "ldap_user_home_directory = canary"
            case constants.ATTR_USER_SHELL:
                assert results[0] == "ldap_user_shell = canary"
            case _:
                assert key is None, f"{key}: Unexpected key"


def test__attribute_map_keys_shadow():
    for key in constants.LDAP_SHADOW_MAP_KEYS:
        data = {"shadow": {key: "canary"}}
        results = utils.attribute_maps_data_to_params(data)
        assert len(results) == 1

        match key:
            case constants.ATTR_SHADOW_OBJ:
                assert results[0] == ""
            case constants.ATTR_SHADOW_LAST_CHANGE:
                assert results[0] == "ldap_user_shadow_last_change = canary"
            case constants.ATTR_SHADOW_MIN:
                assert results[0] == "ldap_user_shadow_min = canary"
            case constants.ATTR_SHADOW_MAX:
                assert results[0] == "ldap_user_shadow_max = canary"
            case constants.ATTR_SHADOW_WARNING:
                assert results[0] == "ldap_user_shadow_warning = canary"
            case constants.ATTR_SHADOW_INACTIVE:
                assert results[0] == "ldap_user_shadow_inactive = canary"
            case constants.ATTR_SHADOW_EXPIRE:
                assert results[0] == "ldap_user_shadow_expire = canary"
            case _:
                assert key is None, f"{key}: Unexpected key"


def test__attribute_map_keys_group():
    for key in constants.LDAP_GROUP_MAP_KEYS:
        data = {"group": {key: "canary"}}
        results = utils.attribute_maps_data_to_params(data)
        assert len(results) == 1

        match key:
            case constants.ATTR_GROUP_OBJ:
                assert results[0] == "ldap_group_object_class = canary"
            case constants.ATTR_GROUP_GID:
                assert results[0] == "ldap_group_gid_number = canary"
            case constants.ATTR_GROUP_MEMBER:
                assert results[0] == "ldap_group_member = canary"
            case _:
                assert key is None, f"{key}: Unexpected key"


def test__attribute_map_keys_netgroup():
    for key in constants.LDAP_NETGROUP_MAP_KEYS:
        data = {"netgroup": {key: "canary"}}
        results = utils.attribute_maps_data_to_params(data)
        assert len(results) == 1

        match key:
            case constants.ATTR_NETGROUP_OBJ:
                assert results[0] == "ldap_netgroup_object_class = canary"
            case constants.ATTR_NETGROUP_MEMBER:
                assert results[0] == "ldap_netgroup_member = canary"
            case constants.ATTR_NETGROUP_TRIPLE:
                assert results[0] == "ldap_netgroup_triple = canary"
            case _:
                assert key is None, f"{key}: Unexpected key"
