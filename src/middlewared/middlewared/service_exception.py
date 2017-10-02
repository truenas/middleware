import errno


class CallException(Exception):
    pass


class CallError(CallException):

    def __init__(self, errmsg, errno=errno.EFAULT):
        self.errmsg = errmsg
        self.errno = errno

    def __str__(self):
        errcode = errno.errorcode.get(self.errno, 'EUNKNOWN')
        return f'[{errcode}] {self.errmsg}'


class ValidationError(CallException):
    """
    ValidationError is an exception used to point when a provided
    attribute of a middleware method is invalid/not allowed.
    """

    def __init__(self, attribute, errmsg, errno=errno.EFAULT):
        self.attribute = attribute
        self.errmsg = errmsg
        self.errno = errno

    def __str__(self):
        errcode = errno.errorcode.get(self.errno, 'EUNKNOWN')
        return f'[{errcode}] {self.attribute}: {self.errmsg}'


class ValidationErrors(CallException):
    """
    CallException with a collection of ValidationError
    """

    def __init__(self, errors=None):
        self.errors = errors or []

    def add(self, attribute, errmsg, errno=errno.EINVAL):
        self.errors.append(ValidationError(attribute, errmsg, errno))

    def add_child(self, attribute, child):
        for e in child.errors:
            self.add(f"{attribute}.{e.attribute}", e.errmsg, e.errno)

    def extend(self, errors):
        for e in errors.errors:
            self.add(e.attribute, e.errmsg, e.errno)

    def __iter__(self):
        for e in self.errors:
            yield e.attribute, e.errmsg, e.errno

    def __bool__(self):
        return bool(self.errors)

    def __str__(self):
        output = ''
        for e in self.errors:
            output += str(e) + '\n'
        return output
