Configuration Database
======================

.. toctree::
   :maxdepth: 1
   :caption: Contents:

   sqlalchemy.rst
   migrations.rst

TrueNAS configuration database is stored in `/data/freenas-v1.db`. It is a SQLite database file containing all system
settings, configured share objects, periodic tasks, etc. in a structured manner.

Database tables structure is defined in corresponding middleware plugins using :doc:`SQLAlchemy <sqlalchemy>`.

Different TrueNAS releases might have different database table structures. While upgrading a TrueNAS installation to a
newer release, a :doc:`database migration <migrations>` process is performed.
