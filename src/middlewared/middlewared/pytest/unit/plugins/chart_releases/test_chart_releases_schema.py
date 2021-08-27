import yaml

from middlewared.plugins.chart_releases_linux.schema import get_schema


questions = yaml.load("""
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


def test__get_schema__handles_immutable():
    schema = get_schema(questions, True, {"host": "0.0.0.0", "port": "8081", "advanced": {"mtu": "9000"}})

    assert schema[0].attrs["host"].default == "127.0.0.1"
    assert schema[0].attrs["host"].editable is True

    assert schema[0].attrs["port"].default == "8081"
    assert schema[0].attrs["port"].editable is False

    assert schema[0].attrs["advanced"].attrs["mtu"].default == "9000"
    assert schema[0].attrs["advanced"].attrs["mtu"].editable is False
