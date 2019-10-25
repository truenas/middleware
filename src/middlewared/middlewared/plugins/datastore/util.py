from middlewared.schema import accepts
from middlewared.service import CallError, private, Service
from middlewared.sqlalchemy import Model

from .schema import SchemaMixin


class DatastoreService(Service, SchemaMixin):

    class Config:
        private = True

    @private
    def get_backrefs(self, name):
        """
        Returns list of (datastore_name, column_name) for all tables that reference this table
        without being ON DELETE CASCADE / ON DELETE SET NULL.
        """
        table = self._get_table(name)

        result = []
        for other_table in Model.metadata.tables.values():
            for column in other_table.c:
                if column.foreign_keys:
                    foreign_key = list(column.foreign_keys)[0]
                    if foreign_key.column.table == table:
                        if foreign_key.ondelete is None:
                            result.append((
                                other_table.name.replace('_', '.', 1),
                                column.name[:-3] if column.name.endswith('_id') else column.name,
                            ))

        return result

    @private
    async def sql(self, query, *args):
        try:
            if query.strip().split()[0].upper() == 'SELECT':
                return [dict(row) for row in await self.middleware.call('datastore.fetchall', query, *args)]
            else:
                await self.middleware.call('datastore.execute', query, *args)
        except Exception as e:
            raise CallError(e)

    @accepts()
    async def dump_json(self):
        models = []
        for table, in await self.middleware.call(
                "datastore.fetchall",
                "SELECT name FROM sqlite_master WHERE type = 'table'"
        ):
            try:
                entries = await self.middleware.call("datastore.sql", f"SELECT * FROM {table}")
            except CallError as e:
                self.logger.debug("%r", e)
                continue

            models.append({
                "table_name": table,
                "verbose_name": table,
                "fields": [
                    {
                        "name": row[1],
                        "verbose_name": row[1],
                        "database_type": row[2],
                    }
                    for row in await self.middleware.call("datastore.fetchall", "PRAGMA table_info('%s');" % table)
                ],
                "entries": entries,
            })

        return models
