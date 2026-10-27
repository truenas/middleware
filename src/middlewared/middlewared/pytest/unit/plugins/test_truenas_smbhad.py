import configparser
import os

from mako.template import Template
import pytest

import middlewared
from middlewared.plugins.etc import FileShouldNotExist

TEMPLATE = os.path.join(os.path.dirname(middlewared.__file__), "etc_files", "truenas_smbhad.conf.mako")


def render(licensed, node):
    render_ctx = {"failover.licensed": licensed, "failover.node": node}
    return Template(filename=TEMPLATE).render(render_ctx=render_ctx, FileShouldNotExist=FileShouldNotExist)


@pytest.mark.parametrize("node", ["A", "B"])
def test_ha_controller_gets_its_node(node):
    conf = configparser.ConfigParser()
    conf.read_string(render(True, node))
    assert {section: dict(conf[section]) for section in conf.sections()} == {"smbhad": {"node": node}}


@pytest.mark.parametrize("licensed,node", [(False, "A"), (False, "MANUAL"), (True, "MANUAL")])
def test_no_file_without_a_known_node(licensed, node):
    with pytest.raises(FileShouldNotExist):
        render(licensed, node)
