import errno


class Error(Exception):

    def __init__(self, attribute, errmsg:str, errno=errno.EINVAL):
        self.attribute = attribute
        self.errmsg = errmsg
        self.errno = errno
        self.extra = None

    def __str__(self):
        return '[{0}] {1}'.format(self.attribute, self.errmsg)


class ResolverError(Exception):
    pass
