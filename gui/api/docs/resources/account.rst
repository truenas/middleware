=========
Account
=========

Resources related to accounts.

bsdUsers
----------

The bsdUsers resource represents all unix users.

==============   ===============
Property         Description
==============   ===============
id               The unique identifier by which to identify the service
...              ...
==============   ===============

List Resource
~~~~~~~~~~~~~~~

.. code-block:: text

    /api/v1.0/account/bsdusers/

GET
+++++

Returns a list of all current users.

.. code-block:: bash

   GET /api/v1.0/account/bsdusers/ HTTP/1.1


POST
++++++

Creates a new user and returns the new user object.

==============   ===============
Param            Description
==============   ===============
...              ...
==============   ===============

.. code-block:: text

   POST /api/v1/account/bsdusers/ HTTP/1.1 bsdusr_username%20myuser


DELETE
++++++

Delete a user.

.. code-block:: text

   DELETE /api/v1/account/bsdusers/:id/ HTTP/1.1
