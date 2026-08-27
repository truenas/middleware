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
a class may narrow the settings catalogue further with `listed_only_when`. Both are documented as
class variables on `AlertClass` and `AlertSource` above.

A declaration does not build its own rule. It names one of the populations from
`middlewared.alert.applicability.vocabulary`:

.. code-block:: python

    from middlewared.alert.applicability import TRUENAS_HARDWARE

    class SomeAlertSource(AlertSource):
        applies_to = TRUENAS_HARDWARE

.. automodule:: middlewared.alert.applicability.vocabulary
    :members:

Every answer comes from `middlewared.alert.applicability.Applicability`, which reads the facts once
and memoizes per declaration. Nothing outside the applicability package reads `applies_to` or
`listed_only_when` -- a second reader is a second answer that can disagree with the first.

The applicability inventory
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Applicability is declared per alert and summarised nowhere, so a one-word change to a rule can add or
remove an alert across a whole class of machines with nothing in the diff to show it. The inventory at
`src/middlewared/middlewared/pytest/unit/alert/inventory/applicability.txt` is there to double-check
exactly that: it records which systems every declaration covers, one line at a time. It is generated,
checked in, and compared byte for byte by `test_applicability_matrix`; its own header explains the
rows and columns.

The answers are asked of the production `Applicability` object rather than recomputed, so the file
cannot drift from what the daemon does.

If you change an alert
^^^^^^^^^^^^^^^^^^^^^^

Regenerate the inventory yourself, in the same commit as the change:

.. code-block:: bash

    cd src/middlewared
    ALERT_MATRIX_REGENERATE=1 PYTHONPATH=. FAKE_ENV=1 pytest-3 \
        middlewared/pytest/unit/alert/test_applicability_matrix.py

Run it from `src/middlewared` with `PYTHONPATH=.` as shown, the same way CI runs the unit suite. From
the repository root the import resolves to the installed `middlewared` rather than your working tree,
and collection fails before the test regenerates anything.

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
moves. `test_a_source_never_outruns_its_classes` does read `check()` to infer which classes a source
produces, so a `check()` that starts creating a different class can fail that test with the inventory
unchanged.

A declaration with no `applies_to` applies everywhere and its inventory row is all `Y`. That is the
right declaration for most alerts, and it is also what forgetting looks like, so the suite cannot flag
it for you in general: `test_every_declaration_carries_a_rule` only checks that a declaration the
inventory records as *restricted* still carries a rule. If your new alert is not meaningful on
commodity hardware, say so explicitly.

What the guard tests mean when they fail
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

All of these live in `middlewared/pytest/unit/alert/`.

`test_applicability_matrix`
    The inventory no longer describes the tree. Regenerate it and read the diff.

`test_every_declaration_carries_a_rule`
    A declaration recorded as restricted has lost its rule, so it now applies everywhere. Restore the
    rule, or regenerate the inventory if the widening is intended.

`test_every_rule_is_a_vocabulary_name`
    A declaration gates on something other than a named population. Add the population to
    `vocabulary` and name it. This is also the only static guard over `alert/source/`, which mypy does
    not check.

`test_rules_are_read_only_where_applicability_is_decided`
    Something outside the applicability package reads `applies_to` or `listed_only_when`. Ask
    `Applicability` instead.

`test_ha_classes_are_not_listed_without_an_ha_license`
    An `AlertCategory.HA` class would be offered in the catalogue on a system with no HA license. Give
    it `listed_only_when = HA_LICENSED`.

`test_a_source_never_outruns_its_classes`
    A source's rule is satisfied where its class's rule is not, so it creates alerts that are stored
    and never shown. Narrow the source or widen the class.

`test_the_flag_carriers_are_what_was_reviewed`
    A second frozen inventory, of the two run gates the applicability matrix deliberately does not
    model. Update it in `test_run_gates.py` when you add or remove `post_failover_blackout` or
    `require_stable_peer`.
