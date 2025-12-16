from . import ldap_constants


def search_base_data_to_params(data):
    """
    This function converts the data from our schema key `search_bases` into
    sssd configuration information
    """
    search_params = []
    for base in ldap_constants.LDAP_SEARCH_BASE_KEYS:
        if not (value := data.get(base)):
            continue

        match base:
            case ldap_constants.SEARCH_BASE_USER:
                search_params.append(f'ldap_user_search_base = {value}')
            case ldap_constants.SEARCH_BASE_GROUP:
                search_params.append(f'ldap_group_search_base = {value}')
            case ldap_constants.SEARCH_BASE_NETGROUP:
                search_params.append(f'ldap_netgroup_search_base = {value}')
            case _:
                raise ValueError(f'{base}: unexpected LDAP search base type')

    return search_params


def attribute_maps_data_to_params(data):
    """
    This function converts the data from our schema key `attribute_maps` into
    sssd configuration information
    """
    map_params = []
    for nss_type, keys in ldap_constants.LDAP_ATTRIBUTE_MAPS.items():
        for key in keys:
            if not (value := data.get(nss_type, {}).get(key)):
                continue

            match key:
                # passwd
                case ldap_constants.ATTR_USER_OBJ:
                    map_params.append(f'ldap_user_object_class = {value}')
                case ldap_constants.ATTR_USER_NAME:
                    map_params.append(f'ldap_user_name = {value}')
                case ldap_constants.ATTR_USER_UID:
                    map_params.append(f'ldap_user_uid_number = {value}')
                case ldap_constants.ATTR_USER_GID:
                    map_params.append(f'ldap_user_gid_number = {value}')
                case ldap_constants.ATTR_USER_GECOS:
                    map_params.append(f'ldap_user_gecos = {value}')
                case ldap_constants.ATTR_USER_HOMEDIR:
                    map_params.append(f'ldap_user_home_directory = {value}')
                case ldap_constants.ATTR_USER_SHELL:
                    map_params.append(f'ldap_user_shell = {value}')

                # shadow
                case ldap_constants.ATTR_SHADOW_OBJ:
                    # SSSD does not support overriding object class for shadow
                    map_params.append('')
                case ldap_constants.ATTR_SHADOW_LAST_CHANGE:
                    map_params.append(f'ldap_user_shadow_last_change = {value}')
                case ldap_constants.ATTR_SHADOW_MIN:
                    map_params.append(f'ldap_user_shadow_min = {value}')
                case ldap_constants.ATTR_SHADOW_MAX:
                    map_params.append(f'ldap_user_shadow_max = {value}')
                case ldap_constants.ATTR_SHADOW_WARNING:
                    map_params.append(f'ldap_user_shadow_warning = {value}')
                case ldap_constants.ATTR_SHADOW_INACTIVE:
                    map_params.append(f'ldap_user_shadow_inactive = {value}')
                case ldap_constants.ATTR_SHADOW_EXPIRE:
                    map_params.append(f'ldap_user_shadow_expire = {value}')

                # group
                case ldap_constants.ATTR_GROUP_OBJ:
                    map_params.append(f'ldap_group_object_class = {value}')
                case ldap_constants.ATTR_GROUP_GID:
                    map_params.append(f'ldap_group_gid_number = {value}')
                case ldap_constants.ATTR_GROUP_MEMBER:
                    map_params.append(f'ldap_group_member = {value}')

                # netgroup
                case ldap_constants.ATTR_NETGROUP_OBJ:
                    map_params.append(f'ldap_netgroup_object_class = {value}')
                case ldap_constants.ATTR_NETGROUP_MEMBER:
                    map_params.append(f'ldap_netgroup_member = {value}')
                case ldap_constants.ATTR_NETGROUP_TRIPLE:
                    map_params.append(f'ldap_netgroup_triple = {value}')
                case _:
                    raise ValueError(f'{key}: unexpected attribute map parameter for {nss_type}')

    return map_params
