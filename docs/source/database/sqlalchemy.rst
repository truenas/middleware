SQLAlchemy
==========

`SQLAlchemy <https://www.sqlalchemy.org>`_ is a powerful SQL toolkit for Python. For our modest purpose of structuring
TrueNAS configuration we only use the following components:

* `Database Abstraction Layer <https://docs.sqlalchemy.org/en/latest/core/engines.html>`_
* `SQL Query Generator <https://docs.sqlalchemy.org/en/14/core/tutorial.html>`_
* `Declarative syntax for table schema <https://docs.sqlalchemy.org/en/latest/orm/extensions/declarative/basic_use.html#defining-attributes>`_
  that is built on top of `Core Metadata <https://docs.sqlalchemy.org/en/latest/core/metadata.html>`_
* `Core Types <https://docs.sqlalchemy.org/en/latest/core/type_basics.html>`_

Database tables are defined as classes in corresponding middleware plugins:

.. literalinclude:: /../../src/middlewared/middlewared/plugins/api_key.py
    :pyobject: APIKeyModel
    :caption:

We override some of the SQLAlchemy defaults with the ones that better serve our needs:

* We import all sqlalchemy types we use into `middlewared/sqlalchemy.py` so we can just do
  :code:`import middlewared.sqlalchemy as sa` in our plugins and use them as e.g. :code:`sa.Integer`
* In vanilla SQLAlchemy columns are nullable by default (you have to type `nullable=False` for each column you want to
  make `NOT NULL`). As most of our columns are not nullable, we’ve changed it so columns are not nullable by default

  .. literalinclude:: /../../src/middlewared/middlewared/sqlalchemy.py
      :pyobject: Column
      :caption:

Every time the database schema is changed, a :doc:`database migration <migrations>` must be created.
