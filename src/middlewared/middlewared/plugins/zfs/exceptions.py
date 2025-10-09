__all__ = ("ZFSPathNotProvidedException", "ZFSPathNotFoundException")


class ZFSPathNotProvidedException(Exception):
    pass


class ZFSPathNotFoundException(Exception):
    def __init__(self, path):
        self.message = f"{path!r} not found"
        super().__init__(self.message)
