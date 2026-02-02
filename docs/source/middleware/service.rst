Service Development Guide
=========================

This document outlines the process for adding new API services to the TrueNAS middleware, including
type annotations and API BaseModel classes. The ``update_`` plugin serves as the reference
implementation for these patterns.

Adding a New API Plugin
-----------------------

Plugin Directory Structure
^^^^^^^^^^^^^^^^^^^^^^^^^^

Create a new directory under ``src/middlewared/middlewared/plugins/`` (e.g., ``myservice/``):

.. code-block:: text

    plugins/myservice/
    ├── __init__.py      # Main service class definition
    ├── implementation.py # Implementation functions
    └── utils.py         # Helper utilities (optional)

The ``__init__.py`` file contains the service class and exports it via ``__all__``.

Service Class Definition
^^^^^^^^^^^^^^^^^^^^^^^^

Define your service class in ``__init__.py``:

.. code-block:: python

    from __future__ import annotations

    from middlewared.service import Service,

    __all__ = ("MyServiceService",)


    class MyServiceService(Service):
        class Config:
            cli_namespace = 'system.myservice'
            role_prefix = 'MYSERVICE'

Registering the Service
^^^^^^^^^^^^^^^^^^^^^^^

Register your service in the ``ServiceContainer`` class located in
``src/middlewared/middlewared/service_container.py``:

.. code-block:: python

    from middlewared.plugins.myservice import MyServiceService

    class ServiceContainer(BaseServiceContainer):
        def __init__(self, middleware: "Middleware"):
            super(ServiceContainer, self).__init__(middleware)

            # ... existing services ...
            self.myservice = MyServiceService(middleware)

The attribute name (``self.myservice``) determines the service namespace in the API
(e.g., ``myservice.my_method``).

Adding Methods
--------------

To add a new API method to your service, follow these steps:

1. Define the API Models
^^^^^^^^^^^^^^^^^^^^^^^^

First, create the ``Args`` and ``Result`` classes in your API module (see `API BaseModel Classes`_):

.. code-block:: python

    class MyServiceMethodArgs(BaseModel):
        name: str
        """Name parameter."""
        count: int = 10
        """Optional count with default value."""


    class MyServiceMethodResult(BaseModel):
        result: bool
        """Whether the operation succeeded."""

2. Import the Models
^^^^^^^^^^^^^^^^^^^^

In your service file, import the models from ``middlewared.api.current``:

.. code-block:: python

    from middlewared.api.current import (
        MyServiceMethodArgs, MyServiceMethodResult,
    )

3. Add the Method
^^^^^^^^^^^^^^^^^

Add the method to your service class with the ``@api_method`` decorator. The method should
delegate to an implementation function defined elsewhere in the package:

.. code-block:: python

    from .implementation import my_method as my_method_impl

    @api_method(
        MyServiceMethodArgs,
        MyServiceMethodResult,
        roles=['MYSERVICE_READ'],
        check_annotations=True,
    )
    async def my_method(self, name: str, count: int) -> bool:
        """
        Method docstring describes what it does.
        """
        return await my_method_impl(self.context, name, count)

The implementation function lives in a separate module (e.g., ``implementation.py``):

.. code-block:: python

    from middlewared.service import ServiceContext

    async def my_method_impl(context: ServiceContext, name: str, count: int) -> bool:
        # Actual implementation here
        return True

This pattern keeps service classes small and focused on API definitions while implementation
logic is organized in separate modules.

Requirements:

- The ``@api_method`` decorator takes the Args class, Result class, and options
- Set ``check_annotations=True`` to verify the API model matches the function signature and
  return type. This will be ``True`` by default in the future. All new methods must have this
  set; methods without it are legacy
- Method parameters must match the fields in the Args class
- Return type annotation must match the ``result`` field type in the Result class
- Add ``roles`` to specify required permissions (e.g., ``MYSERVICE_READ``, ``MYSERVICE_WRITE``)
- Service methods delegate to implementation functions, passing ``self.context`` and arguments

ServiceContext
""""""""""""""

The ``ServiceContext`` object provides access to middleware functionality within implementation
functions. It includes:

- ``context.middleware`` - Access to the middleware instance
- ``context.logger`` - Logger for the service
- ``context.s`` - Type-safe access to other services (and your own) via the service container
- ``context.call2()`` - Type-safe async call to other service methods
- ``context.call_sync2()`` - Type-safe synchronous call to other service methods

To call other services in a type-safe manner, use ``call2``/``call_sync2`` with ``context.s``:

.. code-block:: python

    from middlewared.service import ServiceContext

    async def my_method_impl(context: ServiceContext, name: str) -> dict:
        # Type-safe async call via context.s (service container)
        config = await context.call2(context.s.update.config)

        # Type-safe sync call with arguments
        result = context.call_sync2(context.s.zfs.resource.query_impl, query_params)

        return {'name': name, 'config': config}

The ``context.s`` attribute provides access to the service container with full type information.
Method references like ``context.s.update.config`` are validated at development time, ensuring
correct argument types and return values.

For calling legacy services not yet converted to the type-safe system:

.. code-block:: python

    # String-based calls for legacy services
    pool_config = await context.middleware.call('pool.query')
    system_info = context.middleware.call_sync('system.info')

Private Methods
^^^^^^^^^^^^^^^

Methods that are accessed by other services internally but not exposed publicly through the API
must use the ``@private`` decorator. Keep the number of public API methods as low as possible;
prefer private methods for internal service-to-service communication:

.. code-block:: python

    from .implementation import internal_helper as internal_helper_impl

    @private
    async def internal_helper(self, name: str) -> None:
        return await internal_helper_impl(self.context, name)

API BaseModel Classes
---------------------

Location
^^^^^^^^

Create API models in ``src/middlewared/middlewared/api/v{version}/myservice.py`` where
``{version}`` is the current API version (e.g., ``v26_0``).

Basic Structure
^^^^^^^^^^^^^^^

.. code-block:: python

    from __future__ import annotations

    from typing import Literal

    from middlewared.api.base import (
        BaseModel, Excluded, excluded_field, ForUpdateMetaclass, LongString,
    )

    __all__ = [
        "MyServiceMethodArgs", "MyServiceMethodResult",
    ]

Args and Result Classes
^^^^^^^^^^^^^^^^^^^^^^^

Every API method requires an ``Args`` class and a ``Result`` class:

.. code-block:: python

    class MyServiceMethodArgs(BaseModel):
        pass  # For methods with no arguments


    class MyServiceMethodResult(BaseModel):
        result: MyServiceEntry
        """The service configuration."""

For methods with arguments:

.. code-block:: python

    class MyServiceDownloadArgs(BaseModel):
        url: str
        """URL to download from."""
        timeout: int | None = None
        """Timeout in seconds. Defaults to 30."""


    class MyServiceDownloadResult(BaseModel):
        result: bool
        """Whether the download succeeded."""

Nested Models
^^^^^^^^^^^^^

For complex responses, create nested models:

.. code-block:: python

    class MyServiceStatusDetails(BaseModel):
        state: Literal['RUNNING', 'STOPPED', 'ERROR']
        """Current state."""
        message: str | None
        """Status message."""


    class MyServiceStatus(BaseModel):
        code: Literal['OK', 'ERROR']
        """Status code."""
        details: MyServiceStatusDetails | None
        """Detailed status information."""
