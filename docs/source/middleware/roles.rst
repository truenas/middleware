User Roles
##########

.. contents:: Table of Contents
    :depth: 4

Middleware user role is a string (e.g. `REPLICATION_TASK_READ`) that, being listed in one of the user's privileges,
allows them to execute specific middleware methods.

Defining a role
***************

Roles are defined explicltly in `ROLES` dictionary in `src/middlewared/middlewared/role.py`:

.. automodule:: middlewared.role
   :members: Role,

Allowing roles to execute methods
*********************************

Basic ConfigService/CRUDService methods
=======================================

If you set `role_prefix` attribute of the service's `Config` class to `"SERVICE"`, then the following roles must exist:

* `SERVICE_READ` (and it will have access to calling `service.config` and `service.query` methods)
* `SERVICE_WRITE` (and it will have access to calling `service.create`, `service.update` and `service.delete` methods)

Additionally, if `role_separate_delete` attribute is set to `True`, then `SERVICE_DELETE` role must exist, and it will
have access to calling `service.delete` method (while `SERVICE_WRITE` role alone will not have access to this method).

The common practice is to define the corresponding roles like this:

.. code-block:: python

    ROLES = {
        'SERVICE_READ': Role(),
        'SERVICE_WRITE': Role(includes=['SERVICE_READ']),
        ...
    }

@accepts decorator
==================

Roles for an arbitrary method can be specified using `roles` parameter of the `@accepts` decorator:

.. code-block:: python

    @accepts(
        Int("id"),
        roles=["TASK_RUN"],
    )

When multiple roles are specified, each of them will have access to the decorated method (without requiring others).

Additional checks
*****************

app.authenticated_credentials.has_role
======================================

`app.authenticated_credentials.has_role` method can be used to check if the authenticated user has a specific role.
Please note that in order for `app` object to be available, the method must use `@pass_app` decorator.
