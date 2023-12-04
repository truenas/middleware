import pytest
from unittest.mock import Mock

from middlewared.service_exception import ValidationErrors
from middlewared.schema import (
    accepts, LDAP_DN
)
from middlewared.plugins.ldap_ import constants, utils

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
        "shadow_object_class": None,
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

@pytest.mark.parametrize('value,expected', [
    ('o=5def63d2b12d4332c706a57f,dc=jumpcloud,dc=com', 'o=5def63d2b12d4332c706a57f,dc=jumpcloud,dc=com'),
    ('canary', ValidationErrors),
    (420, ValidationErrors),
])
def test__schema_ldapdn(value, expected):
    @accepts(LDAP_DN('data', null=True))
    def ldapdnnotnull(self, data):
        return data

    self = Mock()

    if expected is ValidationErrors:
        with pytest.raises(expected):
            ldapdnnotnull(self, value)
    else:
        assert ldapdnnotnull(self, value) == expected


def test__schema_ldapdn_null():
    @accepts(LDAP_DN('data', null=True))
    def ldapdnnull(self, data):
        return data

    self = Mock()

    assert ldapdnnull(self, None) is None


def test__freeipa_schema_conversion():
    # This verifies we're not getting unexpected lines added by having NULL entries
    assert len(utils.attribute_maps_data_to_params(FREEIPA_SAMPLE_ATTR_MAPS)) == 0

    search_bases = utils.search_base_data_to_params(FREEIPA_SAMPLE_SEARCH_BASE)
    assert len(search_bases) == 3
    for key, entry in FREEIPA_SAMPLE_SEARCH_BASE.items():
        match key:
            case "base_user":
                assert f'base passwd {entry}' in search_bases
            case "base_group":
                assert f'base group {entry}' in search_bases
            case "base_netgroup":
                assert f'base netgroup {entry}' in search_bases


def test__default_search_base():
    assert len(utils.search_base_data_to_params(NONE_SAMPLE_SEARCH_BASE)) == 0


def test__attribute_map_keys_passwd():
    for key in constants.LDAP_PASSWD_MAP_KEYS:
        data = {"passwd": {key: "canary"}}
        results = utils.attribute_maps_data_to_params(data)
        assert len(results) == 1

        match key:
            case constants.ATTR_USER_OBJ:
                assert results[0] == "filter passwd (objectClass=canary)"
            case constants.ATTR_USER_NAME:
                assert results[0] == "map passwd uid canary"
            case constants.ATTR_USER_UID:
                assert results[0] == "map passwd uidNumber canary"
            case constants.ATTR_USER_GID:
                assert results[0] == "map passwd gidNumber canary"
            case constants.ATTR_USER_GECOS:
                assert results[0] == "map passwd gecos canary"
            case constants.ATTR_USER_HOMEDIR:
                assert results[0] == "map passwd homeDirectory canary"
            case constants.ATTR_USER_SHELL:
                assert results[0] == "map passwd loginShell canary"
            case _:
                assert key is None, f"{key}: Unexpected key"


def test__attribute_map_keys_shadow():
    for key in constants.LDAP_SHADOW_MAP_KEYS:
        data = {"shadow": {key: "canary"}}
        results = utils.attribute_maps_data_to_params(data)
        assert len(results) == 1

        match key:
            case constants.ATTR_SHADOW_OBJ:
                assert results[0] == "filter shadow (objectClass=canary)"
            case constants.ATTR_SHADOW_LAST_CHANGE:
                assert results[0] == "map shadow shadowLastChange canary"
            case constants.ATTR_SHADOW_MIN:
                assert results[0] == "map shadow shadowMin canary"
            case constants.ATTR_SHADOW_MAX:
                assert results[0] == "map shadow shadowMax canary"
            case constants.ATTR_SHADOW_WARNING:
                assert results[0] == "map shadow shadowWarning canary"
            case constants.ATTR_SHADOW_INACTIVE:
                assert results[0] == "map shadow shadowInactive canary"
            case constants.ATTR_SHADOW_EXPIRE:
                assert results[0] == "map shadow shadowExpire canary"
            case _:
                assert key is None, f"{key}: Unexpected key"


def test__attribute_map_keys_group():
    for key in constants.LDAP_GROUP_MAP_KEYS:
        data = {"group": {key: "canary"}}
        results = utils.attribute_maps_data_to_params(data)
        assert len(results) == 1

        match key:
            case constants.ATTR_GROUP_OBJ:
                assert results[0] == "filter group (objectClass=canary)"
            case constants.ATTR_GROUP_GID:
                assert results[0] == "map group gidNumber canary"
            case constants.ATTR_GROUP_MEMBER:
                assert results[0] == "map group member canary"
            case _:
                assert key is None, f"{key}: Unexpected key"


def test__attribute_map_keys_netgroup():
    for key in constants.LDAP_NETGROUP_MAP_KEYS:
        data = {"netgroup": {key: "canary"}}
        results = utils.attribute_maps_data_to_params(data)
        assert len(results) == 1

        match key:
            case constants.ATTR_NETGROUP_OBJ:
                assert results[0] == "filter netgroup (objectClass=canary)"
            case constants.ATTR_NETGROUP_MEMBER:
                assert results[0] == "map netgroup memberNisNetgroup canary"
            case constants.ATTR_NETGROUP_TRIPLE:
                assert results[0] == "map netgroup nisNetgroupTriple canary"
            case _:
                assert key is None, f"{key}: Unexpected key"
