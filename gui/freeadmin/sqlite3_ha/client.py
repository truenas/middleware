from django.db.backends.sqlite3 import base as sqlite3base


class DatabaseClient(sqlite3base.DatabaseClient):
    pass
