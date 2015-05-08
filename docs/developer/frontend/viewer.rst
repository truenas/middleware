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

* ``defaultMode`` - a string representing the view mode that the view should open with by default.
* ``allowedModes`` - an array containing the list of view modes the user should have available.
* ``inputData`` - an array containing the raw data that the view is responsible
  for displaying. This is obtained as needed from the Flux store and can only
  be modified by sending changes to the middleware, not by manipulating data in
  the view.
* :ref:`viewData` - an object containing Viewer metadata, which in turn must contain the following fields:

  * ``format`` - information about the item schema including how to edit certain
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

.. index:: DetailViewer
.. _DetailViewer:

DetailViewer
------------

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
