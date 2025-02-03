Adding A New API Version
========================

.. contents:: Table of Contents
    :depth: 3

When starting to work on a new TrueNAS release, we must generate new stable API version definition.

The first step will be to use the files of the recently released version as a base for the new version:

.. code-block:: bash

    cp -R src/middlewared/middlewared/api/v25_04_0 src/middlewared/middlewared/api/v25_10_0

Then we need to remove all `from_previous` and `to_previous` class method declarations in the new version. This needs
to be done manually.

After that, change `src/middlewared/middlewared/api/current.py` to import from the newly added version instead of
importing from the previously used one:

.. code-block:: python

    from .v25_04_0 import *  # noqa
