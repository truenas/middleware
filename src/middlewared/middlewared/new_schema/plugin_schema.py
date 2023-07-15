class Schemas(dict):

    def add(self, schema):
        if schema.name in self:
            raise ValueError(f'Schema "{schema.name}" is already registered')
        super().__setitem__(schema.name, schema)
