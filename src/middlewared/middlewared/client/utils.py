

class Struct:
    """
    Simpler wrapper to access using object attributes instead of keys.
    This is meant for compatibility when switch scripts to use middleware
    client instead of django directly.
    """
    def __init__(self, mapping):
        for k, v in mapping.iteritems():
            if isinstance(v, dict):
                setattr(self, k, Struct(v))
            else:
                setattr(self, k, v)
