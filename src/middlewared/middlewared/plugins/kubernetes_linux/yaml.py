import yaml


class SafeDumper(yaml.SafeDumper):
    pass


# We would like to customize safe dumper here so that when it dumps values, we quote strings
# why we want to do this is for instances when strings like 'y' are treated as boolean true
# by yaml and if we don't dump this enclosed with quotes, helm treats 'y' as true and we get inconsistent
# usage
yaml.add_representer(
    str, lambda dumper, data: dumper.represent_scalar('tag:yaml.org,2002:str', data, style='"'), SafeDumper
)
