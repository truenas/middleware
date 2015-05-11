.. highlight:: javascript
   :linenothreshold: 5

.. index:: Viewer
.. _Viewer:

The Viewer
==========

The Viewer is the React component that diplays most of the pages in the
FreeNAS 10 UI. It supports three modes of displaying items: Detail, Icon, and
Table. Each mode has a distinct layout for displaying available items and
displaying an item that's been selected.

.. index:: Viewer Props
.. _Viewer Props:

Viewer Props
------------

The Viewer expects certain props.

.. code-block:: javascript

  propTypes: {
      defaultMode  : React.PropTypes.string
    , allowedModes : React.PropTypes.array
    , inputData    : React.PropTypes.array.isRequired
    , viewData     : React.PropTypes.object.isRequired
    , displayData  : React.PropTypes.object // not currently used
  }

* :ref:`defaultMode` - a string representing the view mode that the view should open with by default.
* :ref:`allowedModes` - an array containing the list of view modes the user should have available.
* :ref:`inputData` - an array containing the raw data that the view is responsible
  for displaying. This is obtained as needed from the Flux store and can only
  be modified by sending changes to the middleware, not by manipulating data in
  the view.
* :ref:`viewData` - an object containing Viewer metadata, which in turn must contain the following fields:

  * :ref:`format` - information about the item schema including how to edit certain
    fields and which ones should be used for searching, path names, and certain
    display defaults.
  * ``addEntity`` - string to display on the button for adding a new item of the type
    represented by the view.
  * ``routing`` - information used for setting up routes to the view. It contains
    the following fields:

    * ``route`` - the identifier for the per-route that's specified in routes.js
    * ``param`` - the identifier for the field to be used to create the per-item
      routes, also as specified in routes.js
    * ``addentity`` - the name of the route to be used for adding an item

  * ``display`` - an object containing data used for how the sidebar display will
    group and filter items It contains the following fields:

    * ``filterCriteria`` - all the groupings into which items should be sorted.
      It may contain an arbitrary number of groups. The keys used for each group
      will be used in the rest of the display fields. Each group is an object
      that must contain the following fields:

      * ``name`` - a string that will be used to label the group when it is displayed
      * ``testprop`` - an expression that will be evaluated to determine if an item
        should be considered part of the group. The typical case is just to
        check for a value of a field in the item

    * ``remainingName`` - the string displayed as the name of the group containing
      all otherwise ungrouped items
    * ``ungroupedName`` - also a string to be displayed as the name of the group containing all otherwise ungrouped
      items. fallback from remainingName
    * ``allowedFilters`` - not currently in use?
    * ``defaultFilters`` - not currently working according to a TODO (?)
    * ``allowedGroups`` - not currently in use?
    * ``defaultGroups`` - not currently in use?
    * ``defaultCollapsed`` - an array of strings representing groups that should
      begin in the collapsed state in the sidebar
* ``displayData`` - not currently in use. May have been obsoleted by moving
  ``format`` into ``viewdata``

.. index:: defaultMode
.. _defaultMode:

defaultMode
~~~~~~~~~~~

``defaultMode`` is simply a string specifying the mode that the Viewer should start
with when it first mounts. The accepted strings are:

* "detail" - The DetailViewer will be used when the Viewer mounts.
* "item" - the ItemViewer will be used when the Viewer mounts.
* "table" - the TableViewer will be used when the Viewer mounts.
* "heir" - not yet supported. This is planned for use with a future
  heirarchical view mode.

``defaultMode`` is completely optional. If it is not provided, the default view
mode will be the DetailViewer.

.. index:: allowedModes
.. _allowedModes:

allowedModes
~~~~~~~~~~~~

``allowedModes`` is an array of strings representing the view modes that should
be available to a particular view. The accepted strings are the same as the ones
that should be provided to ``defaultMode``: "detail", "item", and/or "table".

``allowedModes`` is completely optional. If it is not provided, all view modes
will be available to the Viewer.

.. index:: inputData
.. _inputData:

inputData
~~~~~~~~~

``inputData`` is a collection containing all the data that should be
displayed by the viewer. In almost all cases, ``inputData`` will be provided by
the Flux store associated with the view being implemented.

``inputData`` must always be provided, even if it's an empty collection.

.. index:: viewData
.. _viewData:

viewData
~~~~~~~~

viewData is complex object containing metadata about the view rendering the
Viewer. viewData is always required, as are some (but not all) of its fields.

The fields of ``viewData`` are as follows:

.. index::
.. _format:

format
^^^^^^

``format`` provides the viewer with metadata about how the data provided in
``inputData`` should be displayed. It is based largely on the middleware schema
of the data to be displayed.

``format`` allows for arbitrary fields. Any extra metadata that will be used to
display an item belongs here. For example, ``networks-display`` adds a
``fontIconKey`` field that applies the contents of an extra ``font_icon`` field
in ``dataKeys`` to display a FontAwesome icon to represent that item in the
DetailViewer and IconViewer modes.

The following fields are required.

.. index::
.. _dataKeys:

dataKeys
********

.. note:: ``dataKeys`` is typically listed last in the file, but it informs all the other
   fields, so here it will be discussed first.

``dataKeys`` is an array of objects describing every field of the item being
displayed which could be displayed in the Web UI. Generally, it will map to the
schema for that item type. Each object also includes additional data about how
display that field in the GUI. The keys for each field are used to identify the
field use use for the rest of the fields in the ``format`` JSON.

It is possible to add arbitrary objects to dataKeys. This should be done if you
plan to add extra metadata to items in a Flux store that will be used for
display purposes.

The required fields in each object in ``dataKeys`` are:

key
+++

``key`` is the name used to represent this field of the item. Generally this
should be the same as the field in the middleware schema, but anything may be
used. If changes are made, the data fromt he middleware will need to be
modified accordingly in the Flux store for that data.

name
++++

``name`` should be a human friendly string representing the field. Generally it
should be capitalized.

type
++++

``type`` should be the data type the field will hold. This will be used for
multiple purposes, including input validation and display logic.

.. warning:: This must match the type provided in the middleware schema.

formElement
+++++++++++

``formElement`` should be a string matching the name of an html input field
type. For example, "builtin" in the groups dataKeys has the form formElement
"checkbox".

.. note:: In the future, we may support custom input field types, or this field
   may be removed entirely.

mutable
+++++++

``mutable`` should be a boolean representing whether or not the field should
ever be modified by the user.

.. warning:: This must match the value provided in the middleware schema.

defaultCol
++++++++++

``defaultCol`` should be a boolean representing whether or not the field should
be displayed by default in the TableViewer.

.. index::
.. _primarykey:

primaryKey
**********

``primaryKey`` must be a string matching the name of one of the keys in
``dataKeys``. In general, this key should be the most recognizable name for the
item. For example, for a user, the ``primaryKey`` is the username.

It's also very likely that the ``primaryKey`` should represent an object in
``dataKeys`` where ``defaultCol`` is ``true``.

The value of the field identified by ``primarykey`` will be used for several
purposes:

* It will be one of the strings matched when searching in the DetailViewer
* It will be the first string used to label the item in the DetailViewer sidebar
  and IconViewer grid
* It will be used as an input when creating a fallback icon in both DetailViewer
  and IconViewer

.. index::
.. _secondaryKey:

secondaryKey
************

``secondaryKey`` must be a string matching the name of one of the keys in
``dataKeys``. In general, ``secondaryKey`` should be a field that will be useful
for identifying the item or provide useful information about it. For example,
for a service, ``secondaryKey`` is the state of the process (whether it's
running or not).

It's likely that ``secondaryKey`` should represent an object in ``dataKeys``
where ``defaultCol`` is ``true``.

The value of the field identified by ``secondaryKey`` will be used for several
purposes:

* It will be one of the strings matched when searching in the DetailViewer
* It will be the second string used to label the item in the DetailViewer
  sidebar and IconViewer grid
* It will be used as an input when creating a fallback icon in both DetailViewer
  and IconViewer

selectionKey
************

``selectionKey`` must be a string matching the name of one of the keys in
``dataKeys``. ``selectionKey`` should be guaranteed to be unique to the item,
and should be human-friendly if at all possible.

The value of the field identified by ``selectionKey`` will be used for several
purposes:

* It will be the name of the route used to display and access the specific item
  in the web UI.
* It will most likely be used as an alternate means of retrieving item-specific
  data from a Flux store.

uniqueKey
*********

``uniqueKey`` must be a string matching the name of one of keys in ``dataKeys``.
``uniqueKey`` must be unique to the item in all circumstances. It is not
necessary for ``uniqueKey`` to be human-friendly.

Usage of uniqueKey will vary among views. One thing for which it's currently
being used is seeding a PRNG to generate background colors for default icons.

It is acceptable for ``uniqueKey`` and ``selectionKey`` to be identical.

.. index:: DetailViewer
.. _DetailViewer:

DetailViewer
------------

The DetailViewer is the default view mode of the Viewer. It takes the items
provided to the Viewer and displays them in a searchable list on the left side
of the window. When an item is selected, it displays the item in the rest of the
space in the window using the Item view component provided to the viewer.

The DetailViewer also supports an optional button to add a new entity if the
necessary route, label, and component are included. The addEntity button is
placed above the item list search bar.

.. image:: images/viewer/groups_view_detail.png
   :alt: An example of the detail view with an item selected.
The Groups view in detail mode with an item selected.

.. index:: IconViewer
.. _IconViewer:

IconViewer
----------

.. image:: images/viewer/groups_view_icon.png
   :alt: An example of the icon view with no item selected.
The Groups view in icon mode without an item selected.


.. image:: images/viewer/groups_view_icon_selected.png
   :alt: An example of the icon view with an item selected.
The Groups view in icon mode with an item selected.

.. index:: TableViewer
.. _TableViewer:

TableViewer
-----------

.. image:: images/viewer/groups_view_table.png
   :alt: An example of the table view with no item selected.
The Groups view in table mode without an item selected.

.. image:: images/viewer/groups_view_table_selected.png
   :alt: An example of the table view with an item selected.
The Groups view in table mode with an item selected.
