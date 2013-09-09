=========
Account
=========

Resources related to accounts.

bsdUsers
----------

The bsdUsers resource represents all unix users.

========================  ===============
Property                  Description
========================  ===============
id                        The unique identifier by which to identify the service
bsdusr_uid                User ID
bsdusr_username           Username
bsdusr_home               Home Directory Default /nonexistent
bsdusr_shell              Shell
bsdusr_full_name          Full Name
bsdusr_builtin            Built-in User
bsdusr_email              E-mail
bsdusr_password_disabled  Disable password login
bsdusr_locked             Lock user
========================  ===============

List resource
+++++++++++++

Returns a list of all current users.

.. code-block:: bash

   GET /api/v1.0/account/bsdusers/ HTTP/1.1


Create resource
+++++++++++++++

Creates a new user and returns the new user object.

==============   ===============
Param            Description
==============   ===============
...              ...
==============   ===============

.. code-block:: text

   POST /api/v1.0/account/bsdusers/ HTTP/1.1

.. code-block:: js

        {
                "bsdusr_username": "myuser"
        }


Delete resource
+++++++++++++++

Delete a user.

.. code-block:: text

   DELETE /api/v1.0/account/bsdusers/:id/ HTTP/1.1


Change password
+++++++++++++++

Change a user password.

===============  ===============
Param            Description
===============  ===============
bsdusr_password  New password
===============  ===============

.. code-block:: text

   POST /api/v1.0/account/bsdusers/:id/password HTTP/1.1

.. code-block:: js

        {
                "bsdusr_password": "new"
        }


Get user groups
++++++++++++++++

Get a list of groups of that user.

.. code-block:: text

   GET /api/v1.0/account/bsdusers/:id/groups/ HTTP/1.1


Set user groups
++++++++++++++++

Set groups of a user.

.. code-block:: text

   POST /api/v1.0/account/bsdusers/:id/groups/ HTTP/1.1

.. code-block:: js

        [
                "wheel",
                "ftp"
        ]
