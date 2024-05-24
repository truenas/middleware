from .constants import SMBSharePreset


def smb_strip_comments(auxparam_in):
    """
    Strips out all comments from auxiliary parameters and returns
    as new-line separated list.
    """
    parsed_config = ""
    for entry in auxparam_in.splitlines():
        entry = entry.strip()
        if entry == "" or entry.startswith(('#', ';')):
            continue

        # For some reason user may have added more comments after the value
        # For example "socket options = IPTOS_LOWDELAY # I read about this on the internet"
        entry = entry.split("#")[0].strip()
        parsed_config += entry if len(parsed_config) == 0 else f'\n{entry}'

    return parsed_config


def auxsmbconf_dict(aux, direction="TO"):
    """
    Auxiliary parameters may be converted freely between key-value form and
    concatenated strings. This method either goes from string `TO` a dict or
    `FROM` a dict into a string.
    """
    match direction:
        case 'TO':
            if not isinstance(aux, str):
                raise ValueError(f'{type(aux)}: wrong input type. Expected str.')

            ret = {}
            stripped = smb_strip_comments(aux)
            for entry in stripped.splitlines():
                kv = entry.split('=', 1)
                ret[kv[0].strip()] = kv[1].strip()

            return ret

        case 'FROM':
            if not isinstance(aux, dict):
                raise ValueError(f'{type(aux)}: wrong input type. Expected dict.')

            return '\n'.join([f'{k}={v}' if v is not None else k for k, v in aux.items()])

        case _:
            raise ValueError(f'{direction}: unexpected conversion direction')


def apply_presets(data_in):
    """
    Apply settings from presets. Only include auxiliary parameters
    from preset if user-defined aux parameters already exist. In this
    case user-defined takes precedence.
    """
    data = data_in.copy()
    params = (SMBSharePreset[data["purpose"]].value)["params"].copy()
    if data.get('home'):
        params.pop('path_suffix', None)

    aux = params.pop("auxsmbconf")
    data.update(params)
    if data["auxsmbconf"]:
        preset_aux = auxsmbconf_dict(aux, direction="TO")
        data_aux = auxsmbconf_dict(data["auxsmbconf"], direction="TO")
        preset_aux.update(data_aux)
        data["auxsmbconf"] = auxsmbconf_dict(preset_aux, direction="FROM")

    return data


def is_time_machine_share(share):
    return share.get('timemachine', False) or share.get('purpose') in [SMBSharePreset.TIMEMACHINE.name, SMBSharePreset.ENHANCED_TIMEMACHINE.name]
