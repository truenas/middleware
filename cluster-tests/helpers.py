def get_bool(parm):
    if isinstance(parm, bool):
        return parm

    if isinstance(parm, str):
        if parm.lower() == 'false':
            return False
        if parm.lower() == 'true':
            return True
        raise ValueError(parm)

    return bool(parm)
