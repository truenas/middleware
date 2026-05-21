API Version Aliases
===================

.. contents:: Table of Contents
    :depth: 3

Sometimes a new TrueNAS release ships without any changes to the API surface (for example, a maintenance release that
only fixes bugs in service implementations). In that situation we do not want to duplicate an entire ``api/vXX_YY_ZZ``
package just to advertise the new version number. Instead, the middleware lets us register the new version as an alias
of an existing one.

Adding a new alias
------------------

To declare that a new release uses the exact same API as a previously released one, edit
``src/middlewared/middlewared/api/aliases.py`` and add an entry to the ``aliases`` dictionary. The key is the new
version, the value is the existing version it should mirror:

.. code-block:: python

    aliases = {
        "v25.10.3": "v25.10.2",
        "v25.10.4": "v25.10.2",
    }

In the example above, both ``v25.10.3`` and ``v25.10.4`` are served from the models defined under
``middlewared/api/v25_10_2``. No ``v25_10_3`` or ``v25_10_4`` package needs to exist on disk.

When to use an alias instead of a new version
---------------------------------------------

Use an alias when:

* The release introduces no changes to API models, method signatures, or return types.
* You only need the new version number to be advertised so that clients can pin to it.

Do **not** use an alias when:

* Any model field is added, removed, renamed, or has its type changed.
* Any method is added or removed.
* You need ``from_previous`` / ``to_previous`` adapters between this version and the previous one.

In those cases follow the procedure described in :doc:`new_version` instead.
