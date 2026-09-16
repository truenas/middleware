API Model Field Markers
=======================

.. contents:: Table of Contents
    :depth: 3

The type annotation of an API model field can carry a marker that changes how middleware treats the field, beyond
validating its value. Three are in use: ``Secret``, ``Private`` and ``FullAdmin``. Each answers a different question
about the field, so a field may carry more than one; ``FullAdmin[Secret[dict]]`` is valid and in use.

All three are exported by ``middlewared.api.base``.

Choosing a marker
-----------------

Ask these questions about every new or changed field of a public API model, in this order:

1. Is the value a password, key, token, passphrase, or anything else a caller must not be shown back?
   Wrap it in ``Secret``.
2. Does the field exist for middleware's own use, with no reason for an API caller to ever set it?
   Wrap it in ``Private``.
3. Does middleware pass the value through to a root command line, or interpolate it into the configuration file of
   a privileged daemon, without constraining what it may contain?
   Wrap it in ``FullAdmin``.
4. Is the value interpolated bare into a line-oriented configuration file, where a line break would let the caller
   append a directive of their own?
   Use ``SingleLineString`` (or ``SingleLineNonEmptyString``) on the model that accepts writes.

A ``Literal``, a port, an IP address, or any other field whose validator fully constrains the value needs none of
these.

Secret
------

``Secret[T]`` marks a value that is stored and used by middleware but must not be shown back to most callers.

.. code-block:: python

    class MyServiceEntry(BaseModel):
        password: Secret[str] = Field(description="Password used to authenticate to the remote.")
        passphrase: Secret[str | None] = Field(default=None, description="Passphrase for the private key.")

What it does:

* When a method's result is serialized for an API caller, every ``Secret`` field is replaced by a placeholder
  unless the caller holds ``FULL_ADMIN`` or the ``<role_prefix>_WRITE`` role of the service that returned it.
* Internal code that needs the real value calls ``model.model_dump(expose_secrets=True)``. A plain
  ``model_dump()`` returns the placeholder, so a value that is forwarded to another method or written to a
  configuration file must be dumped with ``expose_secrets=True``.
* A default on a ``Secret`` field is wrapped for you, so ``Secret[str] = Field(default="")`` compares equal to a
  supplied empty string.

``Secret`` must wrap the whole field. ``Secret[str | None]`` is correct; ``Secret[str] | None`` is rejected when
the model is built, because the redaction is not honored inside a union member.

Private
-------

``Private[T]`` marks a field that is internal to middleware.

.. code-block:: python

    class MyServiceCreate(BaseModel):
        name: str = Field(description="Name of the entry.")
        generated_id: Private[str | None] = Field(default=None, description="Filled in by middleware.")

What it does:

* The field is left out of the published API schema, exactly like pydantic's ``SkipJsonSchema``.
* A caller who supplies a value other than the field's default gets ``Extra inputs are not permitted``, the same
  error an unknown key produces, so the field is indistinguishable from one that does not exist.
* Internal calls through ``middleware.call`` may set it. That is the point: a method routinely forwards its own
  validated params to another method, and only middleware is allowed to fill these in along the way.

FullAdmin
---------

``FullAdmin[T]`` marks a field that only a ``FULL_ADMIN`` credential may set or change, on an endpoint that
otherwise stays open to its ordinary roles.

Why it exists
^^^^^^^^^^^^^

Several endpoints take a free-form field whose value middleware hands straight to something that runs as root:
extra flags for a command line, or lines appended verbatim to the configuration file of a privileged daemon. A role
such as ``SSH_WRITE`` or ``SNAPSHOT_TASK_WRITE`` is meant to let its holder configure that one service. Such a
field turns it into arbitrary command execution as root: ``rsynctask.extra`` becomes rsync flags, and ``-e`` names
the program rsync spawns; ``ssh.options`` is interpolated verbatim into ``sshd_config``; ``ups.shutdowncmd`` is
what upsmon runs as root. The role guarding the endpoint was never meant to grant that.

Removing the field, or hiding it behind ``Private``, would take the capability away from full administrators who
have a legitimate use for it. ``FullAdmin`` keeps the field in the API and restricts who may mutate it.

What it does
^^^^^^^^^^^^

.. code-block:: python

    class RsyncTaskCreate(BaseModel):
        ...
        extra: FullAdmin[list[str]] = Field(default_factory=list, description="Extra rsync arguments.")

* The field stays in the published schema, and the restriction is appended to its description automatically, so an
  API caller can see why a validation error came back.
* ``CRUDService.create``, ``CRUDService.update`` and ``ConfigService.update`` check the payload before the plugin's
  ``do_create`` or ``do_update`` runs. Marking the field is all a plugin has to do.
* On create, a value that differs from the field's default is rejected. On update, only a value that differs from
  what is currently stored is rejected, so a client that reads an entry, edits an unrelated field and writes the
  whole thing back is unaffected.
* Internal calls (no ``app``), the HA peer, and any caller who already holds ``FULL_ADMIN`` are not checked.
* A rejection is a ``ValidationError`` on the field, with the message
  ``Only a user with the `FULL_ADMIN` role may set or change this field.``
* A method that accepts an entry-shaped payload but does not go through those wrappers (``cloudsync.sync_onetime``
  is one) must call ``middlewared.service.full_admin.check_full_admin_model`` itself. The unit test
  ``test_full_admin_fields_are_enforced`` fails if a marked field is reachable through a public method with no
  enforcement path, so a forgotten call does not get past CI.

When to use it
^^^^^^^^^^^^^^

Use ``FullAdmin`` when the value of the field reaches, unvalidated:

* the argument list of a process that runs as root (rsync, rclone, QEMU, a Docker Compose file);
* a configuration file read by a daemon that runs as root or with elevated privileges (sshd, snmpd, proftpd, NUT);
* the kernel command line.

A field whose documentation says "additional options", "extra arguments" or "auxiliary parameters" almost always
qualifies.

Do not use it when:

* The whole endpoint exists to grant the capability, so there is no auxiliary field to single out. Gate the case in
  the plugin instead, with ``app_needs_full_admin_check`` from ``middlewared.utils.privilege``; ``tunable.create``
  does this for udev rules and for the usermode-helper sysctls.
* A validator already constrains the value fully.

Marking a field fences off nothing on its own if a sibling field reaches the same file unconstrained. A line break in
any field interpolated bare into a line-oriented configuration file lets the caller append the very directives the
marked field exists to deny. Constrain those siblings with ``SingleLineString`` on the model that accepts writes
(``UPSUpdate``, ``SNMPUpdate`` and ``SSHUpdate`` do this), and not on the entry model: ``config`` and ``update`` read
the stored entry first, so a constraint on the entry would make a value stored before the constraint existed break
both, with no way to repair it through the API.

Review with Claude
------------------

Whether a field needs one of these markers is the kind of judgment that is easy to miss when the field is one line in
a larger change, and the consequence of missing ``FullAdmin`` is a privilege escalation. When you add or change a
field of a public API model, have Claude review the model before you open the pull request.

The repository's ``CLAUDE.md`` carries the checklist from `Choosing a marker`_, so Claude Code applies it on its own
when it edits or reviews a file under ``src/middlewared/middlewared/api/``. To ask for the review explicitly, run
``/code-review`` on the branch, or prompt it directly:

.. code-block:: text

    Review the API model changes on this branch. For every added or changed field, say whether it
    needs Secret, Private, FullAdmin or SingleLineString, and why. Trace where each value ends up
    (command line, configuration file, database) before deciding.

Treat the answer as a second pair of eyes, not as sign-off: the reviewer still confirms where the value ends up, and
the unit tests still have to pass.
