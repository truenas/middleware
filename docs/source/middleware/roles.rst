User Roles
##########

.. contents:: Table of Contents
    :depth: 4

Middleware user role is a string (e.g. `REPLICATION_TASK_READ`) that, being listed in one of the user's privileges,
allows them to execute specific middleware methods.

NOTE: sensitive fields are redacted in output of middleware methods when the user lacks full administrator and also
lacks the WRITE role corresponding with `role_prefix` specified in the middleware plugin class configuration.

Defining a role
***************

Roles are defined explicltly in `ROLES` dictionary in `src/middlewared/middlewared/role.py`:

.. automodule:: middlewared.role
   :members: Role,

Allowing roles to execute methods
*********************************

Implicitly populated roles
==========================

`FULL_ADMIN` role will have access to calling all methods.

`READONLY_ADMIN` role will have access to calling `service.config`, `service.get_instance`, `service.query` and all
`service.*_choices` methods of all services.

Basic ConfigService/CRUDService methods
=======================================

If you set `role_prefix` attribute of the service's `Config` class to `"SERVICE"`, then the following roles must exist:

* `SERVICE_READ` (and it will have access to calling `service.config`, `service.get_instance`, `service.query` and all
  `service.*_choices` methods)
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

@api_method decorator
==================

Roles for an arbitrary method can be specified using `roles` parameter of the `@api_method` decorator:

.. code-block:: python

    @api_method(MethodArgs, MethodResult, roles=["TASK_RUN"])

When multiple roles are specified, each of them will have access to the decorated method (without requiring others).

@filterable_api_method decorator
=====================

Roles for methods that are decorated with `@filterable_api_method` may be specified using the `roles` parameter:

.. code-block:: python

   @filterable_api_method(item=ItemEntry, roles=['REPORTING_READ'])

Subscribable event roles
========================

Roles for subscribable events may be specified using the `roles` parameter in the `Event` constructor:

.. code-block:: python

    Event(
        name="alert.list",
        description="Sent on alert changes.",
        roles=["ALERT_LIST_READ"],
        models={
            "ADDED": AlertListAddedEvent,
            "CHANGED": AlertListChangedEvent,
            "REMOVED": AlertListRemovedEvent,
        },
    ),

`SERVICE_READ` roles will have access to the corresponding `service.query` event. `READONLY_ADMIN` will have access to
all `service.query` events for all CRUD services.

Additional checks
*****************

app.authenticated_credentials.has_role
======================================

`app.authenticated_credentials.has_role` method can be used to check if the authenticated user has a specific role.
Please note that in order for `app` object to be available, the method must use `@pass_app` decorator.

middleware jobs
===============

`job.credentials` contains the authenticated credentials for the user and may be used for additional checks within
the job. Credentials will be set to None for internal jobs. In this case the credential should be treated as
full admin.
