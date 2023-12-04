from middlewared.schema import Dict, Str, LDAP_DN


# Different server_types that we can auto-detect
SERVER_TYPE_ACTIVE_DIRECTORY = 'ACTIVE_DIRECTORY'
SERVER_TYPE_FREEIPA = 'FREEIPA'
SERVER_TYPE_GENERIC = 'GENERIC'
SERVER_TYPE_OPENLDAP = 'OPENLDAP'

# keys for search_bases in our LDAP plugin schema
SEARCH_BASE_USER = 'base_user'
SEARCH_BASE_GROUP = 'base_group'
SEARCH_BASE_NETGROUP = 'base_netgroup'

# keys for `passwd` attribute map
ATTR_USER_OBJ = 'user_object_class'
ATTR_USER_NAME = 'user_name'
ATTR_USER_UID = 'user_uid'
ATTR_USER_GID = 'user_gid'
ATTR_USER_GECOS = 'user_gecos'
ATTR_USER_HOMEDIR = 'user_home_directory'
ATTR_USER_SHELL = 'user_shell'

# keys for `shadow` attribute map
ATTR_SHADOW_OBJ = 'shadow_object_class'
ATTR_SHADOW_LAST_CHANGE = 'shadow_last_change'
ATTR_SHADOW_MIN = 'shadow_min'
ATTR_SHADOW_MAX = 'shadow_max'
ATTR_SHADOW_WARNING = 'shadow_warning'
ATTR_SHADOW_INACTIVE = 'shadow_inactive'
ATTR_SHADOW_EXPIRE = 'shadow_expire'

# keys for `group` attribute map
ATTR_GROUP_OBJ = 'group_object_class'
ATTR_GROUP_GID = 'group_gid'
ATTR_GROUP_MEMBER = 'group_member'

# keys for `netgroup` attribute map
ATTR_NETGROUP_OBJ = 'netgroup_object_class'
ATTR_NETGROUP_MEMBER = 'netgroup_member'
ATTR_NETGROUP_TRIPLE = 'netgroup_triple'

LDAP_SEARCH_BASE_KEYS = [
    SEARCH_BASE_USER,
    SEARCH_BASE_GROUP,
    SEARCH_BASE_NETGROUP,
]

LDAP_PASSWD_MAP_KEYS = [
    ATTR_USER_OBJ,
    ATTR_USER_NAME,
    ATTR_USER_UID,
    ATTR_USER_GID,
    ATTR_USER_GECOS,
    ATTR_USER_HOMEDIR,
    ATTR_USER_SHELL,
]

LDAP_SHADOW_MAP_KEYS = [
    ATTR_SHADOW_OBJ,
    ATTR_SHADOW_LAST_CHANGE,
    ATTR_SHADOW_MIN,
    ATTR_SHADOW_MAX,
    ATTR_SHADOW_WARNING,
    ATTR_SHADOW_INACTIVE,
    ATTR_SHADOW_EXPIRE,
]

LDAP_GROUP_MAP_KEYS = [
    ATTR_GROUP_OBJ,
    ATTR_GROUP_GID,
    ATTR_GROUP_MEMBER
]

LDAP_NETGROUP_MAP_KEYS = [
    ATTR_NETGROUP_OBJ,
    ATTR_NETGROUP_MEMBER,
    ATTR_NETGROUP_TRIPLE
]

LDAP_MAP_KEYS = set.union(
    set(LDAP_PASSWD_MAP_KEYS),
    set(LDAP_SHADOW_MAP_KEYS),
    set(LDAP_GROUP_MAP_KEYS),
    set(LDAP_NETGROUP_MAP_KEYS),
)

LDAP_ADVANCED_KEYS = set(LDAP_SEARCH_BASE_KEYS) | LDAP_MAP_KEYS

# Below are middleware schema configurations for advanced LDAP parameters
LDAP_SEARCH_BASES_SCHEMA_NAME = 'search_bases'
LDAP_SEARCH_BASES_SCHEMA = Dict(
    LDAP_SEARCH_BASES_SCHEMA_NAME,
    LDAP_DN(SEARCH_BASE_USER, null=True),
    LDAP_DN(SEARCH_BASE_GROUP, null=True),
    LDAP_DN(SEARCH_BASE_NETGROUP, null=True),
)

LDAP_PASSWD_MAP_SCHEMA_NAME = 'passwd'
LDAP_PASSWD_MAP_SCHEMA = Dict(
    LDAP_PASSWD_MAP_SCHEMA_NAME,
    Str(ATTR_USER_OBJ, null=True),
    Str(ATTR_USER_NAME, null=True),
    Str(ATTR_USER_UID, null=True),
    Str(ATTR_USER_GID, null=True),
    Str(ATTR_USER_GECOS, null=True),
    Str(ATTR_USER_HOMEDIR, null=True),
    Str(ATTR_USER_SHELL, null=True)
)

LDAP_SHADOW_MAP_SCHEMA_NAME = 'shadow'
LDAP_SHADOW_MAP_SCHEMA = Dict(
    LDAP_SHADOW_MAP_SCHEMA_NAME,
    Str(ATTR_SHADOW_OBJ, null=True),
    Str(ATTR_SHADOW_LAST_CHANGE, null=True),
    Str(ATTR_SHADOW_MIN, null=True),
    Str(ATTR_SHADOW_MAX, null=True),
    Str(ATTR_SHADOW_WARNING, null=True),
    Str(ATTR_SHADOW_INACTIVE, null=True),
    Str(ATTR_SHADOW_EXPIRE, null=True)
)

LDAP_GROUP_MAP_SCHEMA_NAME = 'group'
LDAP_GROUP_MAP_SCHEMA = Dict(
    LDAP_GROUP_MAP_SCHEMA_NAME,
    Str(ATTR_GROUP_OBJ, null=True),
    Str(ATTR_GROUP_GID, null=True),
    Str(ATTR_GROUP_MEMBER, null=True)
)

LDAP_NETGROUP_MAP_SCHEMA_NAME = 'netgroup'
LDAP_NETGROUP_MAP_SCHEMA = Dict(
    LDAP_NETGROUP_MAP_SCHEMA_NAME,
    Str(ATTR_NETGROUP_OBJ, null=True),
    Str(ATTR_NETGROUP_MEMBER, null=True),
    Str(ATTR_NETGROUP_TRIPLE, null=True)
)

LDAP_ATTRIBUTE_MAP_SCHEMA_NAME = 'attribute_maps'
LDAP_ATTRIBUTE_MAP_SCHEMA = Dict(
    LDAP_ATTRIBUTE_MAP_SCHEMA_NAME,
    LDAP_PASSWD_MAP_SCHEMA,
    LDAP_SHADOW_MAP_SCHEMA,
    LDAP_GROUP_MAP_SCHEMA,
    LDAP_NETGROUP_MAP_SCHEMA
)

LDAP_ATTRIBUTE_MAP_SCHEMA_NAMES = [
    LDAP_PASSWD_MAP_SCHEMA_NAME,
    LDAP_SHADOW_MAP_SCHEMA_NAME,
    LDAP_GROUP_MAP_SCHEMA_NAME,
    LDAP_NETGROUP_MAP_SCHEMA_NAME
]
