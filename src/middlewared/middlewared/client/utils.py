

class Struct:
    """
    Simpler wrapper to access using object attributes instead of keys.
    This is meant for compatibility when switch scripts to use middleware
    client instead of django directly.
    """
    def __init__(self, mapping):
        self.__dict__.update(**mapping)
