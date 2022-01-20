import pytest
import yaml

from middlewared.plugins.kubernetes_linux.yaml import SafeDumper


@pytest.mark.parametrize("reference", [
    {'name': 'booltest_true', 'value': True},
    {'name': 'booltest_false', 'value': False},
    {'name': 'str_y', 'value': 'y'},
    {'name': 'str_n', 'value': 'n'},
    {'name': 'str_random', 'value': 'random'},
    {'name': 'str_int', 'value': '1'},
    {'name': 'int_val', 'value': 1},
    {'name': 'float_val', 'value': 1.3},
    {'name': 'list_val', 'value': []},
    {'name': 'list_dict_val', 'value': [{'a': 'y', 'b': 'n', 'c': 'some', 'd': 1}]},
])
def test_yaml_load_dump(reference):
    assert reference == yaml.safe_load(yaml.dump(reference, Dumper=SafeDumper))
    assert reference == yaml.safe_load(yaml.dump(reference, Dumper=yaml.SafeDumper))
