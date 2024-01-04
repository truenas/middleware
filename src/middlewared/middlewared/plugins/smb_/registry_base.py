class RegObj():
    def __init__(self, name, smbconf, default, **kwargs):
        self.name = name
        self.smbconf = smbconf
        self.default = default
        self.smbconf_parser = kwargs.get("smbconf_parser", None)
        self.schema_parser = kwargs.get("schema_parser", None)
        self.middleware = kwargs.get("middleware", None)


class RegistrySchema():
    def __init__(self, schema):
        self.schema = schema

    def _normalize_config(self, conf):
        for v in conf.values():
            if type(v.get('parsed')) == list:
                v['raw'] = ' '.join(v['parsed'])
            elif not v.get('raw'):
                v['raw'] = str(v['parsed'])
        return

    def convert_schema_to_registry(self, data_in, data_out):
        """
        This function converts the our schema into smb.conf
        parameters. Where there is trivial / noncomplex / 1-1
        mapping, the parameter gets directly mapped. In
        Cases where mapping is complex, a parser function is
        supplied for the schema member.
        """
        map_ = self.schema_map()
        for entry, val in data_in.items():
            regobj = map_.get(entry)
            if regobj is None:
                continue

            if regobj.schema_parser is not None:
                regobj.schema_parser(regobj, val, data_in, data_out)
                continue

            if val is None:
                data_out[regobj.smbconf] = {"parsed": ""}

            data_out[regobj.smbconf] = {"parsed": val}

        self._normalize_config(data_out)
        return

    def schema_map(self):
        return {x.name: x for x in self.schema}

    def schema_items(self):
        return [x.name for x in self.schema]
