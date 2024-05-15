import pytest
import random
import string
import yaml

from middlewared.plugins.chart_releases_linux.schema import get_schema
from middlewared.service_exception import ValidationErrors


random_string = "".join(random.choices(string.ascii_letters, k=2048))

questions = yaml.safe_load("""
variable: config
schema:
  type: dict
  attrs:
    - variable: host
      schema:
        type: string
        default: "127.0.0.1"

    - variable: port
      schema:
        type: string
        default: "8080"
        immutable: true

    - variable: advanced
      schema:
        type: dict
        attrs:
          - variable: mtu
            schema:
              type: string
              default: "1500"
              immutable: true
""")

yaml_string = """
variable: config
schema:
  type: dict
  attrs:
    - variable: test_string1
      schema:
        type: string
        max_length: 1024
    - variable: test_string2
      schema:
        type: string
        max_length: 3072
"""

string_max_length_test = yaml.safe_load(yaml_string)


def test__get_schema__handles_immutable():
    schema = get_schema(questions, True, {
        "config": {"host": "0.0.0.0", "port": "8081", "advanced": {"mtu": "9000"}}
    })

    assert schema[0].attrs["host"].default == "127.0.0.1"
    assert schema[0].attrs["host"].editable is True

    assert schema[0].attrs["port"].default == "8081"
    assert schema[0].attrs["port"].editable is False

    assert schema[0].attrs["advanced"].attrs["mtu"].default == "9000"
    assert schema[0].attrs["advanced"].attrs["mtu"].editable is False


def test__string_schema__max_length():
    schema = get_schema(string_max_length_test, True)[0].attrs

    with pytest.raises(ValidationErrors) as e:
        schema["test_string1"].validate(random_string)

    assert e.value.errors[0].errmsg == "The value may not be longer than 1024 characters"
    assert schema["test_string2"].validate(random_string) is None
