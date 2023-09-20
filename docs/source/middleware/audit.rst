Audit
#####

.. contents:: Table of Contents
    :depth: 4

Audit facility allows to log certain events to `/var/log/truenas_audit.log`

Logging method calls
********************

In order to log specific method call to audit log, use `audit` and `audit_extended` parameters of the `@accepts`
decorator:

.. code-block:: python

    @accepts(
        Dict(
            'user_create',
            LocalUsername('username', required=True),
        ),
        audit='Create user',
        audit_extended=lambda data: data["username"],
    )

`audit` is the constant string that will be logged any time the method is called. Additionally, you can specify
`audit_extended` function that will accept the same arguments as the decorated function (without any pre-processing)
and will return the string that will be appended to the audit message to be logged. If an exception occurs in that
function, it will be silently ignored, and only `audit` string will be logged.
