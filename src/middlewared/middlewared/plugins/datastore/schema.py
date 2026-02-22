from sqlalchemy import inspect

from middlewared.sqlalchemy import Model


class SchemaMixin:
    def _get_table(self, name):
        """Look up the SQLAlchemy Table for a dotted datastore name (e.g. "account.bsdusers")."""
        return Model.metadata.tables[name.replace('.', '_').lower()]

    def _get_pk(self, table):
        """Return the primary key Column for table."""
        return [col for col in table.c if col.primary_key][0]

    def _get_col(self, table, name, prefix=None):
        """Look up a column by name, optionally retrying with prefix prepended.

        Delegates to _get_col_by_django_name which also checks for a trailing _id
        variant. Raises KeyError if the column cannot be found.
        """
        col = self._get_col_by_django_name(table, name)
        if col is not None:
            return col

        if prefix:
            col = self._get_col_by_django_name(table, prefix + name)
            if col is not None:
                return col

        raise KeyError(name)

    def _get_col_by_django_name(self, table, name):
        """Return the column for `name` or `name_id`, or None if neither exists.

        The _id suffix variant handles Django-style FK columns where the ORM name
        omits the suffix but the database column carries it.
        """
        if name in table.c:
            return table.c[name]

        if f'{name}_id' in table.c:
            return table.c[f'{name}_id']

    def _get_relationships(self, table):
        """Return the SQLAlchemy relationship map for the ORM model that owns table."""
        for model in Model.registry._class_registry.values():
            if hasattr(model, "__tablename__") and model.__tablename__ == table.name:
                break
        else:
            raise RuntimeError("Could not find model for table %s" % table.name)

        return inspect(model).relationships
