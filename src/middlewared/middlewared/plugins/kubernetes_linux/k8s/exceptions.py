class ApiException(Exception):
    def __init__(self, errmsg):
        self.errmsg = errmsg

    def __str__(self) -> str:
        return self.errmsg
