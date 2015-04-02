from django.db.backends.sqlite3 import base as sqlite3base


class DatabaseIntrospection(sqlite3base.DatabaseIntrospection):
    pass
