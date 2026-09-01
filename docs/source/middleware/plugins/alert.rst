`alert` plugin: Alerts
======================

.. contents:: Table of Contents
    :depth: 3

Alerts are a way to inform the user about various problems in the system (from an expiring SSL certificate to a hardware
fault). Alerts are created either by a periodical checking process or as a reaction to a system event. Then they are
sent via E-Mail/Slack/etc. and also displayed in the UI.

Alert classes
-------------

.. autoclass:: middlewared.alert.base.AlertClass

Structure of an alert
---------------------

.. autoclass:: middlewared.alert.base.Alert

How alerts are created
----------------------

Periodical checkers
^^^^^^^^^^^^^^^^^^^

You can subclass `AlertSource` class (or one of its helper subclasses) to add a new periodical alert checker.

.. autoclass:: middlewared.alert.base.AlertSource
    :members:

One-shot alerts
^^^^^^^^^^^^^^^

One-shot alerts are the alerts created by external events. The main issue with such alerts is deleting them, so there
are a few one-shot alert types, each offering a different deletion strategy.

Add `OneShotAlertClass` to your `AlertClass` superclass list to make it a one-shot alert.

.. autoclass:: middlewared.alert.base.OneShotAlertClass
    :members:

For most use-cases a simple implementation is sufficient:

.. autoclass:: middlewared.alert.base.SimpleOneShotAlertClass

Use the following methods to create/delete one-shot alerts:

.. autoclass:: middlewared.plugins.alert.AlertService
    :members: oneshot_create, oneshot_delete

Which systems an alert applies to
---------------------------------

Not every alert is meaningful on every machine. A declaration says which systems it applies to on two
independent axes -- what the hardware is, and what the license grants -- by setting `applies_to`, and
a class may narrow the settings catalogue further with `listed_only_when`. `applies_to` is documented
as a class variable on both `AlertClass` and `AlertSource` above; `listed_only_when` exists on
`AlertClass` only.

A declaration does not build its own rule. It names one of the populations from
`middlewared.alert.applicability.vocabulary`:

.. code-block:: python

    from middlewared.alert.applicability import TRUENAS_HARDWARE

    class SomeAlertSource(AlertSource):
        applies_to = TRUENAS_HARDWARE

.. automodule:: middlewared.alert.applicability.vocabulary
    :members:

Every answer comes from `middlewared.alert.applicability.Applicability`, which is handed one reading
of the facts and memoizes per declaration. Nothing outside that package may read `applies_to` or
`listed_only_when` -- a second reader is a second answer that can disagree with the first. A guard
test enforces it.

The applicability inventory
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Applicability is declared per alert and summarised nowhere, so a one-word change to a rule can add or
remove an alert across a whole class of machines with nothing in the diff to show it. The inventory at
`src/middlewared/middlewared/pytest/unit/alert/inventory/applicability.txt` is there to double-check
exactly that: it records which systems every declaration covers, one line at a time. It is generated,
checked in, and compared byte for byte by `test_applicability_matrix`; its own header explains the
rows and columns.

If you change an alert
^^^^^^^^^^^^^^^^^^^^^^

Regenerate the inventory yourself, in the same commit as the change:

.. code-block:: bash

    cd src/middlewared
    ALERT_MATRIX_REGENERATE=1 PYTHONPATH=. FAKE_ENV=1 pytest-3 \
        middlewared/pytest/unit/alert/test_applicability_matrix.py

Run it from `src/middlewared`; from the repository root the import resolves to the installed
`middlewared` and collection fails before anything is regenerated.

Then read `git diff` on the inventory. Every changed line is a real change to the set of machines that
sees an alert; if a line moved that you did not mean to move, the rule is wrong, so fix the rule rather
than accept the file. Never edit the inventory by hand, and describe any population change in the
commit message -- reviewing those lines is the whole point of checking the file in.

Regenerate when you:

- add or remove an alert class or an alert source;
- rename an alert class (its `name`) or an alert source class;
- change `applies_to` or `listed_only_when` anywhere;
- change what a population covers, or add a new one;
- change the entitlement policy behind `HA_LICENSED`.

You do not need to when you only change an alert's text, level or the body of `check()` -- no cell
moves. `test_a_source_never_outruns_its_classes` does read the whole body of a source class, not just
`check()`, to infer which classes it produces, so a source that starts naming a different class can
fail that test with the inventory unchanged.

A declaration with no `applies_to` applies everywhere and its inventory row is all `Y`. That is the
right declaration for most alerts, and it is also what forgetting looks like, so the suite cannot flag
it for you in general: `test_every_declaration_carries_a_rule` only checks that a declaration the
inventory records as *restricted* still carries a rule. If your new alert is not meaningful on
commodity hardware, say so explicitly.

What the guard tests mean when they fail
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The guards live in `middlewared/pytest/unit/alert/`. Read the failing test's docstring; a failure is
a real change to which machines see an alert, not a test that needs relaxing.
