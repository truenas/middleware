__author__ = 'jceel'

import sysctl


def get_sysctl(name):
    node = sysctl.filter(name)

    if len(node) == 1:
        return node[0].value

    return {i.name[len(name) + 1:]: i.value for i in node}