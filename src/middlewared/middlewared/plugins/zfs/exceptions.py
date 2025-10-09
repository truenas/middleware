__all__ = ("ZFSFSNotProvidedError", "ZFSPathNotFoundException")


class ZFSFSNotProvidedError(Exception):
    pass


class ZFSPathNotFoundException(Exception):
    def __init__(self, path):
        self.message = f"{path!r} not found"
        super().__init__(self.message)
