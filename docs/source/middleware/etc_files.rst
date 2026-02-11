etc_files Directory
==================

This directory contains template and script files used by the ``etc`` plugin to generate system configuration files in
``/etc/``. The plugin manages configuration file generation, change detection, and proper file permissions.

File Types
----------

Files in this directory must be either:

1. **Mako templates** (``.mako`` extension) - Preferred for most use cases
2. **Python scripts** (``.py`` extension) - Used when complex logic or system operations are required

Mako Templates
^^^^^^^^^^^^^^

Mako templates use templating syntax to generate configuration files. Templates have access to:

- ``middleware`` - The middleware instance for making API calls
- ``service`` - The EtcService instance
- ``FileShouldNotExist`` - Exception class to signal that a file should be removed
- ``render_ctx`` - Dictionary containing pre-fetched API call results (see below)

Example::

    <%
        config = middleware.call_sync('some.config')
    %>
    Setting=${config['value']}

Python Scripts
^^^^^^^^^^^^^^

Python scripts must define a ``render()`` function with one of these signatures::

    def render(service, middleware):
        """For entries without a render context"""
        return content  # bytes or str

    def render(service, middleware, render_ctx):
        """For entries with a render context"""
        return content  # bytes or str

The function can be synchronous or async (``async def``).

**Important**: Python scripts should return the file contents as ``bytes`` or ``str`` so the etc plugin can properly track
changes using ``write_if_changed()``. Scripts that write files directly (returning ``None``) bypass change detection.

To signal that a file should not exist::

    from middlewared.plugins.etc import FileShouldNotExist
    raise FileShouldNotExist

Render Context
--------------

The ``render_ctx`` is a dictionary of pre-fetched API call results passed to templates and scripts. It is defined in the
group configuration in ``etc.py``.

Configuration
^^^^^^^^^^^^^

Groups in ``etc.py`` can specify a ``ctx`` list to pre-fetch data::

    'groupname': {
        'ctx': [
            {'method': 'system.security.config'},
            {'method': 'user.query', 'args': [[['local', '=', True]]]},
        ],
        'entries': [...]
    }

Structure
^^^^^^^^^

The render_ctx dictionary contains:

- **Key**: Method name (e.g., ``'system.security.config'``)

  - If ``ctx_prefix`` is specified, key becomes ``'prefix.method'`` (e.g., ``'tcp.nvmet.port.transport_address_choices'``)

- **Value**: Result of calling the middleware method with specified args

Usage in Templates
^^^^^^^^^^^^^^^^^^

::

    % if render_ctx['failover.licensed']:
        Licensed features enabled
    % endif

Usage in Python Scripts
^^^^^^^^^^^^^^^^^^^^^^^^

::

    def render(service, middleware, render_ctx):
        users = render_ctx['user.query']
        security = render_ctx['system.security.config']

        # Generate configuration content
        return content.encode()

File Registration
-----------------

Files must be registered in the ``GROUPS`` dictionary in ``src/middlewared/middlewared/plugins/etc.py``. Each entry specifies:

- ``type`` - Either ``'mako'`` or ``'py'``
- ``path`` - Path relative to this directory (or use ``local_path`` for different source path)
- ``mode`` - File permissions (optional, default: 0o644)
- ``owner``/``group`` - File ownership (optional, default: root:root)
- ``checkpoint`` - Generation checkpoint (optional, default: 'initial')

Example::

    'groupname': [
        {'type': 'mako', 'path': 'config.conf', 'mode': 0o600},
        {'type': 'py', 'path': 'setup_script'},
    ]
