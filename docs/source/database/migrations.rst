Database Migrations
===================

.. contents:: Table of Contents
    :depth: 3

Database migration is a process of changing the structure of an older TrueNAS release database file to make it work with
a newer TrueNAS release: adding new tables, adding new columns into existing tables, changing database records values...
This is achieved by running small pieces of python code, each of them is also called a database migration.

We use `Alembic <https://alembic.sqlalchemy.org/en/latest/>`_ as a tool that will automatically generate these
migrations based on detected table schema declaration change, and run them in the correct order.

Generating a database migration
-------------------------------

To generate a migration after schema changes run:

.. code-block:: bash

    cd /usr/lib/python3/dist-packages/middlewared
    alembic revision --autogenerate

A new file will appear under :substitution-code:`alembic/versions/|version|`. Rename it to reflect migration contents.
Update the first comment (`"""empty message`) to add a short human-readable description for the migration. Next in
this file you'll find `upgrade` and `downgrade` functions that are used to apply and revert the migration.
Sometimes this automatically generated code will be correct out of the box, in other cases it might need to be
corrected. `downgrade` function can be ignored, because we don't do downgrades.

Adding a new column to an existing table
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The most common type of migration is adding a new column to an existing table. This is also a case where automatically
generated migration will fail most of the time. Imagine we added a new non-nullable column `cert_add_to_trusted_store`
to the `system_certificateauthority` table. Alembic will generate us the following migration:

.. code-block:: python

    def upgrade():
        with op.batch_alter_table('system_certificateauthority', schema=None) as batch_op:
            batch_op.add_column(sa.Column('cert_add_to_trusted_store', sa.Boolean(), nullable=False))

This won't work if `system_certificateauthority` table has rows: SQLite will not have a default value for new column
and will try to set it to `NULL` which will fail. We must specify a `server_default=` value when adding new columns
that must have a non-null value:

  .. literalinclude:: /../../src/middlewared/middlewared/alembic/versions/22.02/2021-08-19_09-30_ca_trusted_store.py
      :pyobject: upgrade
      :caption:

We can also have a dynamic default value by first adding a nullable column, setting the column's value and then changing
this column to `NOT NULL`:

  .. literalinclude:: /../../src/middlewared/middlewared/alembic/versions/12.0/2019-12-19_15-02_alert_last_occurrence.py
      :pyobject: upgrade
      :caption:

Running database migrations
---------------------------

To execute all unapplied migrations run:

.. code-block:: bash

    migrate

As SQLite does not support schema changes within transactions, each statement is executed immediately, and if a
migration crashes in the middle of its execution, you might be left with database in an inconsistent state from which
you won't be able to migrate. To avoid this, always do a backup of `/data/freenas-v1.db` before testing your migrations.

Merging database migrations
---------------------------

Alembic migrations are like git commits: they follow each other in a list (or a tree), and the most recent one (which is
called head) represents the actual state of the database. As in git, you can't have more than one head. If you have
more than one head (e.g. while you've worked on your branch, someone pushed another migration), you simply have to run:

.. code-block:: bash

    cd /usr/lib/python3/dist-packages/middlewared
    alembic merge heads

And a new migration file will appear that will merge all heads. Rename if to the `%Y-%m-%d_%H-%M_merge.py` format.
Update update the first comment `"""empty message` to be `"""Merge`.
Beware that corresponding migration branches can be executed in any order (which is usually not an issue).

Backporting migrations
----------------------

If you know that you'll need to backport a feature you're working into a stable branch, it would be more convenient to
generate your migration in the stable branch first. Then just cherry-pick all your code into the master branch and
generate a merging migration.

.. note::
    The reason for this is the following. Let stable branch have migrations `a → b` and `b → c`, and master
    branch have migrations `a → b`, `b → c` and `c → d`. If you generate a new migration in master branch, it will
    be a migration which parent is ``d``, and it will fail to apply in stable branch because stable branch has no
    `c → d` migration.

All migrations that were created in the stable branch must be backported to the master branch. Otherwise, TrueNAS
upgrade will break.

.. note::
    Let stable branch most recent migration be `xxx → yyy` and master branch most recent migration be `xxx → zzz`.
    An attempt to upgrade from stable branch (where `HEAD` is `yyy`) to master branch will fail as master branch
    code does not know nothing about `yyy` migration; the situation will be similar to the "detached head state"
    in git.

.. warning::
    This section is only talking about migration tree consistency and disregards the database upgrade logic itself.
    Two migrations with same `upgrade` function definition but different `revision` and `down_revision` variable values
    are considered to be different migrations and, if the migration tree is correct, they both will be executed (and if
    the tree is not correct then TrueNAS upgrade will fail). For example, if you try to backport a migration from
    master branch to stable branch by copying it and changing `revision` and `down_revision` variable values, you will
    just introduce a new migration and you will have to backport it back to ensure the tree correctness.

Cherry-picking migrations
^^^^^^^^^^^^^^^^^^^^^^^^^

If a nightly build with some migration that should be backported to the stable branch has already been released,
you have to do the following:

* Switch to the stable branch, cherry-pick the code, remove master migration file and generate the same migration (it
  will be the same `upgrade` code, but different file name, `revision` and `down_revision` values).
* Change the code to be idempotent so it won't fail if the corresponding DB changes were already made.
* Merge newly created stable branch migration to the master branch.
* Also make the original master migration code idempotent (highly likely, it'll just be the same code as in stable
  branch).

Applicability of database migrations
------------------------------------

Migrations should never use middleware client as middleware is not running while doing migrations. For the same reason
migrations can not read anything from user data pools as they are not imported while doing migrations. If you need to
read or modify data stored in the user data pool, use :doc:`data migrations <../middleware/plugins/migration>` instead.

Migrations tips
---------------

* Migrations should import as less modules from middleware as possible. The best way would be to even copy the code or
  re-implement it with as simple approach as possible to prevent accidental retroactive migrations behavior changes in
  the future.
* Always ensure that you leave no table schema definition changes that are not reflected in the migrations. If not sure,
  just generate a new migration and ensure that the `upgrade` function is empty. In other case, the next developer
  generating migration will see unexpected `upgrade` code and will have to figure out whether those are valid changes
  or just an error.
* When merging a long-open PR that contains a migration, ensure that no other PRs involving migrations were merged
  meanwhile. If so, you can just rebase your PR and generate a merge migration or just change `Revised` comment and
  `down_revision` variable in your new migration file (and also rename it with a future date so the file name order
  keeps matching migrations execution order).
* If someone forgot to do the above and CI build failes, just generate a merge migration yourself.
* To run custom SQL do:

  .. code-block:: python

      op.execute("UPDATE system_failover SET master_node = 'A'")

* Here is an example of how to run a SELECT query and iterate over result and how to update a table contents:

  .. literalinclude:: /../../src/middlewared/middlewared/alembic/versions/12.0/2019-09-27_07-44_drop_nfs_share_path_mtm.py
      :pyobject: upgrade
      :caption:

* `with op.batch_alter_table` block is used to group multiple table alterations into one. This is necessary for
  performance reasons, because SQLite `ALTER TABLE` support is limited and for many table schema changes alembic has
  to simply re-create the table. Grouping such changes will help to avoid re-creating the table multiple times.
  Inside this block you can’t run anything else (e.g. custom SQL).

* If you have any questions, don’t hesitate to ask Vladimir Vinogradenko for help

Appendix A: Workflows
---------------------

Workflow 1: Changing the database structure in the master branch
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

#. Perform table definition schema changes in the corresponding middleware plugins. This might include creating new
   tables, adding fields to existing tables, renaming fields, removing fields and tables. This step can be skipped if
   no schema changes is planned (e.g. migration will only affect table contents).
#. :ref:`Generate a database migration file <Generating a database migration>`
#. Rename the newly created file to reflect its purpose. Keep the generated date prefix so migration files are listed
   by the order of their execution. Also add short human-readable migration description to the first comment in this
   file.
#. Make sure that generated `upgrade` function reflects all the changes you made into the table structure. Fix the
   autogenerated code if necessary.
#. Make a database backup (`cp /data/freenas-v1.db /data/freenas-v1.db.bak`)
#. :ref:`Run your migration to test it<Running database migrations>`. If it fails, restore the database file from
   backup, fix the migration and run it again. You might also want to test your migration with a different table data
   if your migration involves changing table rows.
#. Your database changes are ready, you may now start working on changing the middleware plugin code.

Workflow 2: Changing the database structure in the stable branch
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This workflow should always be used for any database schema changes that we want in the stable branch

#. Check out stable branch, :ref:`perform database schema changes <Workflow 1: Changing the database structure in the
   master branch>` there.
#. Switch to the master branch, cherry-pick the code from the stable branch.
#. :ref:`Generate a merge migration<Merging database migrations>`
#. Your database changes are now ready to be tested in the master branch.
