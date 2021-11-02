`migration` plugin: Data migrations
===================================

.. contents:: Table of Contents
    :depth: 3

`migration` helps us to perform post-update operations that involve accessing data stored on user ZFS pool, network
resources or performing other operations that are impossible during the :doc:`database migration
<../../database/migrations>`.

Data migrations are executed right at the end of the boot process when the network is already set up and all the data
pools are imported.

Creating a data migration
-------------------------

Create a file named `middlewared/migration/00xx_migration_name.py` and define either `def migrate(middleware):` or
`async def migrate(middleware):` function there.

Data migrations are executed in the file name order. Executed migrations files names are stored in the database and
so each migration is only executed once.
