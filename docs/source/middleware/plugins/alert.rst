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
