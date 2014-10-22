__author__ = 'jceel'

from freebsd import read_sysctl
from lxml import etree

def confxml():
    return etree.fromstring(read_sysctl("kern.geom.confxml"))