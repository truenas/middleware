from middlewared.plugins.vm.utils import create_element # noqa


def disk_from_number(number):
    return chr(number + 96)
