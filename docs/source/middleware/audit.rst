Audit facility
##############

.. contents:: Table of Contents
    :depth: 4

Audit facility allows to log certain events to `/var/log/truenas_audit.log`

Logging method calls
********************

In order to log specific method call to audit log, use `audit`, `audit_extended` and `audit_callback` parameters of the
`@api_method` decorator:

.. code-block:: python

    @api_method(
        UserCreateArgs,
        UserCreateResult,
        audit='Create user',
        audit_extended=lambda data: data["username"],
    )

`audit` is the constant string that will be logged any time the method is called. Additionally, you can specify
`audit_extended` function that will accept the same arguments as the decorated function (without any pre-processing)
and will return the string that will be appended to the audit message to be logged. If an exception occurs in that
function, it will be silently ignored, and only `audit` string will be logged.

`audit_callback` provides an ability to further append to the logged audit string from inside the method. If it is
`True` then additional `audit_callback` argument will be passed to the function before other arguments:

.. code-block:: python

    @api_method(
        UserUpdateArgs,
        UserUpdateResult,
        audit='Update user',
        audit_callback=True,
    )
    def update(self, audit_callback, pk, data):
        user = self.middleware.call_sync('user.get_instance', pk)
        audit_callback(user['username'])

        # If `audit_callback` line is reached (i.e. if `user.get_instance` throws no exception) then the logged audit
        # string will be `Update user {user['username']}`
