import errno
import subprocess

from .client import ErrnoMixin


def get_errname(code):
    return errno.errorcode.get(code) or ErrnoMixin._get_errname(code) or 'EUNKNOWN'


class CallException(ErrnoMixin, Exception):
    pass


class CallError(CallException):
    def __init__(self, errmsg, errno=errno.EFAULT, extra=None):
        self.errmsg = errmsg
        self.errno = errno
        self.extra = extra

    def __str__(self):
        errname = get_errname(self.errno)
        return f'[{errname}] {self.errmsg}'


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
        errname = get_errname(self.errno)
        return f'[{errname}] {self.attribute}: {self.errmsg}'


class ValidationErrors(CallException):
    """
    CallException with a collection of ValidationError
    """

    def __init__(self, errors=None):
        self.errors = errors or []

    def add(self, attribute, errmsg, errno=errno.EINVAL):
        self.errors.append(ValidationError(attribute, errmsg, errno))

    def add_validation_error(self, validation_error):
        self.errors.append(validation_error)

    def add_child(self, attribute, child):
        for e in child.errors:
            self.add(f"{attribute}.{e.attribute}", e.errmsg, e.errno)

    def check(self):
        if self:
            raise self

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

    def __contains__(self, item):
        # check if an error exists for a given attribute ( item )
        return item in [e.attribute for e in self.errors]


def adapt_exception(e):
    from .utils.shell import join_commandline

    if isinstance(e, subprocess.CalledProcessError):
        if isinstance(e.cmd, (list, tuple)):
            cmd = join_commandline(e.cmd)
        else:
            cmd = e.cmd

        stdout = e.stdout or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", "ignore")
        stderr = e.stderr or ""
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", "ignore")
        output = ''.join([stdout, stderr]).rstrip()

        return CallError(f'Command {cmd} failed (code {e.returncode}):\n{output}')


class MatchNotFound(IndexError):
    """Raised when there is no matching id eg: filter_utils/datastore.query"""
    pass
