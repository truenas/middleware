def smb_strip_comments(auxparam_in):
    parsed_config = ""
    for entry in auxparam_in.splitlines():
        if entry == "" or entry.startswith(('#', ';')):
            continue

        # For some reason user may have added more comments after the value
        # For example "socket options = IPTOS_LOWDELAY # I read about this on the internet"
        entry = entry.split("#")[0].strip()
        parsed_config += entry if len(parsed_config) == 0 else f'\n{entry}'

    return parsed_config
