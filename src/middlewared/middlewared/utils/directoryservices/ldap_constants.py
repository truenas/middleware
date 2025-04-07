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

LDAP_SEARCH_BASE_KEYS = (
    SEARCH_BASE_USER,
    SEARCH_BASE_GROUP,
    SEARCH_BASE_NETGROUP,
)

LDAP_PASSWD_MAP_KEYS = (
    ATTR_USER_OBJ,
    ATTR_USER_NAME,
    ATTR_USER_UID,
    ATTR_USER_GID,
    ATTR_USER_GECOS,
    ATTR_USER_HOMEDIR,
    ATTR_USER_SHELL,
)

LDAP_SHADOW_MAP_KEYS = (
    ATTR_SHADOW_OBJ,
    ATTR_SHADOW_LAST_CHANGE,
    ATTR_SHADOW_MIN,
    ATTR_SHADOW_MAX,
    ATTR_SHADOW_WARNING,
    ATTR_SHADOW_INACTIVE,
    ATTR_SHADOW_EXPIRE,
)

LDAP_GROUP_MAP_KEYS = (
    ATTR_GROUP_OBJ,
    ATTR_GROUP_GID,
    ATTR_GROUP_MEMBER
)

LDAP_NETGROUP_MAP_KEYS = (
    ATTR_NETGROUP_OBJ,
    ATTR_NETGROUP_MEMBER,
    ATTR_NETGROUP_TRIPLE
)

LDAP_MAP_KEYS = frozenset(set.union(
    frozenset(LDAP_PASSWD_MAP_KEYS),
    frozenset(LDAP_SHADOW_MAP_KEYS),
    frozenset(LDAP_GROUP_MAP_KEYS),
    frozenset(LDAP_NETGROUP_MAP_KEYS),
))

LDAP_ADVANCED_KEYS = set(LDAP_SEARCH_BASE_KEYS) | LDAP_MAP_KEYS

LDAP_SEARCH_BASES_SCHEMA_NAME = 'search_bases'
LDAP_PASSWD_MAP_SCHEMA_NAME = 'passwd'
LDAP_SHADOW_MAP_SCHEMA_NAME = 'shadow'
LDAP_GROUP_MAP_SCHEMA_NAME = 'group'
LDAP_NETGROUP_MAP_SCHEMA_NAME = 'netgroup'
LDAP_ATTRIBUTE_MAP_SCHEMA_NAME = 'attribute_maps'
