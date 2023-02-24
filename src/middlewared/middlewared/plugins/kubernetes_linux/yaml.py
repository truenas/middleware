import yaml

class NoDatesFullLoader(yaml.FullLoader):
    @classmethod
    def remove_implicit_resolver(cls, tag_to_remove):
        """
        Remove implicit resolvers for a particular tag

        Takes care not to modify resolvers in super classes.

        We want to load datetimes as strings, not dates, because we
        go on to serialise as json which doesn't have the advanced types
        of yaml, and leads to incompatibilities down the track.
        """
        if not 'yaml_implicit_resolvers' in cls.__dict__:
            cls.yaml_implicit_resolvers = cls.yaml_implicit_resolvers.copy()

        for first_letter, mappings in cls.yaml_implicit_resolvers.items():
            cls.yaml_implicit_resolvers[first_letter] = [(tag, regexp) 
                                                         for tag, regexp in mappings
                                                         if tag != tag_to_remove]

NoDatesFullLoader.remove_implicit_resolver('tag:yaml.org,2002:timestamp')


class SafeDumper(yaml.SafeDumper):
    pass


# We would like to customize safe dumper here so that when it dumps values, we quote strings
# why we want to do this is for instances when strings like 'y' are treated as boolean true
# by yaml and if we don't dump this enclosed with quotes, helm treats 'y' as true and we get inconsistent
# usage
yaml.add_representer(
    str, lambda dumper, data: dumper.represent_scalar('tag:yaml.org,2002:str', data, style='"'), SafeDumper
)
