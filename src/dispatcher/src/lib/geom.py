__author__ = 'jceel'

from freebsd import get_sysctl
from lxml import etree


def confxml():
    return etree.fromstring(get_sysctl("kern.geom.confxml"))