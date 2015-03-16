from django.db.backends.sqlite3 import base as sqlite3base


class DatabaseCreation(sqlite3base.DatabaseCreation):
    pass
