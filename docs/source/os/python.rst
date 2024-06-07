Python
======

.. contents:: Table of Contents
    :depth: 3

Third-party python modules
--------------------------

TrueNAS uses system-wide python environment and relies on Debian repository to install python packages. However, some
of the required python packages are absent there, and others are outdated.

TrueNAS builder uses `python-truenas-requirements <https://github.com/truenas/python-truenas-requirements>`_ script to
generate `deb` packages from `requirements.txt`. Each python package gets one corresponding `deb` package with the
correct name, version and dependencies set; such packages integrate into TrueNAS Debian installation perfectly.

Adding a new third-party python module or upgrading an existing python module
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

#. Add python module in question and all its dependencies into `requirements.txt`. Try to add as few as
   possible; if one of the module's dependencies is shipped with Debian, its better to install it using apt.
#. Run `generate.py` using the exact same Python version as TrueNAS. The easiest way to do this is using Docker:

    .. code-block:: shell

        ./generate.sh

#. Ensure that the resulting diff is a small as possible. Use `constraints.txt` to pin down some indirect dependencies
   to the versions shipped with Debian.

Upgrading all third-party python modules
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Run `requirements-update.py` script to automatically update all items from `requirements.txt` to their latest versions.

Removing unused python modules
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Run `requirements-remove-unused.py` script **on the most recent TrueNAS build** to automatically remove
`requirements.txt` entries that are were not used by that most recent build.

This should be done when some of the python dependencies for TrueNAS components (middleware, CLI, etc.) were removed,
or when apt mirrors were updated (providing official newer versions of the python packages we were previously building
ourselves).
