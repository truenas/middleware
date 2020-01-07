from sqlalchemy import inspect

from middlewared.sqlalchemy import Model


class SchemaMixin:
    def _get_table(self, name):
        return Model.metadata.tables[name.replace('.', '_').lower()]

    def _get_pk(self, table):
        return [col for col in table.c if col.primary_key][0]

    def _get_col(self, table, name, prefix=None):
        col = self._get_col_by_django_name(table, name)
        if col is not None:
            return col

        if prefix:
            col = self._get_col_by_django_name(table, prefix + name)
            if col is not None:
                return col

        raise KeyError(name)

    def _get_col_by_django_name(self, table, name):
        if name in table.c:
            return table.c[name]

        if f'{name}_id' in table.c:
            return table.c[f'{name}_id']

    def _get_relationships(self, table):
        for model in Model._decl_class_registry.values():
            if hasattr(model, "__tablename__") and model.__tablename__ == table.name:
                break
        else:
            raise RuntimeError("Could not find model for table %s" % table.name)

        return inspect(model).relationships
