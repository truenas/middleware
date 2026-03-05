__all__ = ("ZpoolNotFoundException",)


class ZpoolNotFoundException(Exception):
    def __init__(self, pool: str):
        self.message = f"{pool!r} not found"
        super().__init__(self.message)
