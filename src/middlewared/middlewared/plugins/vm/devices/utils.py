import string

from middlewared.plugins.vm.utils import create_element, LIBVIRT_URI # noqa


def disk_from_number(number):
    def i_divmod(n):
        a, b = divmod(n, 26)
        if b == 0:
            return a - 1, b + 26
        return a, b

    chars = []
    while number > 0:
        number, d = i_divmod(number)
        chars.append(string.ascii_lowercase[d - 1])
    return ''.join(reversed(chars))
