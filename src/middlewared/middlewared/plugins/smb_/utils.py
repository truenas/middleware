from secrets import randbits
from middlewared.utils.smb import SMBSharePurpose
from middlewared.plugins.smb_.constants import SMBShareField as share_field


def random_sid():
    """ See MS-DTYP 2.4.2 SID """
    subauth_1 = randbits(32)
    subauth_2 = randbits(32)
    subauth_3 = randbits(32)

    return f'S-1-5-21-{subauth_1}-{subauth_2}-{subauth_3}'


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


def is_time_machine_share(data: dict) -> bool:
    match data[share_field.PURPOSE]:
        case SMBSharePurpose.TIMEMACHINE_SHARE:
            return True
        case SMBSharePurpose.LEGACY_SHARE:
            return data[share_field.OPTS][share_field.TIMEMACHINE]
        case _:
            return False


def get_share_name(data: dict) -> str:
    if data[share_field.PURPOSE] != SMBSharePurpose.LEGACY_SHARE:
        return data[share_field.NAME]

    if data[share_field.OPTS].get(share_field.HOME):
        return 'homes'

    return data[share_field.NAME]
