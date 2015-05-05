.. highlight:: javascript
  :linenothreshold: 5

.. index:: Routing
.. _Routing:

Routing
=======

The technology FreeNAS 10 uses for routing is
`react-router <https://github.com/rackt/react-router>`__. react-router is
not officially part of React, but it shares many developers and uses avant-garde
React features. As of this writing, the public docs for react-router are at
`rackt.github.io/react-router/ <http://rackt.github.io/react-router/>`__.

Because the FreeNAS 10 GUI uses client-side routing, the
page is never refreshed or changed during a session. One of the
interesting effects of this is the ability to use client-side
routing - meaning that as the visible React components are changed
or selected, the route in the browser bar changes to reflect that.

For instance, a simple route would look like this:

.. code-block:: javascript

  <Route name    = "groups"
         path    = "groups"
         handler = { Groups } />

The ``name`` is used to identify the route internally. The ``path`` is the
string that will appear in the browser when that path is active. Finally,
``handler`` is the component that will be rendered with router-specific props
and lifecycle functions. For example, when you navigate to
``myfreenas.local/Accounts/Groups``, the Router renders a RouteHandler which
renders the Groups component with the extra router props and lifecycle functions.

.. warning:: Do not add a route without a working handler. Attempting to load a
   Route with an invalid Route Handler will result in an Internal Server Error.

Routes can be nested inside another Route. ``groups`` itself is nested inside
the ``accounts`` route, which in turn is nested inside the root route, ``/``.
In the example below, ``add-group`` is nested inside ``groups``. This creates
the route ``myfreenas.local/accounts/groups/add-group``. Static nested routes
like this are used when the name of a route will never need to change. Routes
for the main parts of the UI are all static, as are the routes to add new
entities.

.. code-block:: javascript

  <Route name    = "groups"
         path    = "groups"
         handler = { Groups }>
    <Route name    = "add-group"
           path    = "add-group"
           handler = { AddGroup } />
  </Route>

Dynamic Routing
---------------

The dynamic portion of a path has the form ``:paramname``. A Link to a dynamic
path has a ``params`` prop that contains the approprate object to be used as the
dynamic part of the path. For example, a Link to the ``wheel`` group would look
like ``<Link to = "groups-editor" params = { groupID: "wheel" }>
{visualcontent}</Link>``. The path upon clicking that link would be
``myfreenas.local/accounts/groups/wheel``. The Route nesting used to produce
this behavior is as follows:

.. code-block:: javascript

  <Route name    = "groups"
         path    = "groups"
         handler = { Groups }>
    <Route name    = "add-group"
           path    = "add-group"
           handler = { AddGroup } />
    <Route name    = "groups-editor"
           path    = "/groups/:groupID"
           handler = { GroupsItem } />
  </Route>

The Link above loads the ``groups-editor`` path with ``wheel`` as the groupID
param. When the RouteHandler (in this case, GroupsItem) is rendered, is has
access to the param and the active route, and is able in turn to render the
correct item. This works even if the item was loaded directly from the URL.

.. warning:: Any static route must be nested before the dynamic route, because
   otherwise the dynamic route will attempt to pass the param to its handler
   and the intended static route will fail to load. This also means in this case
   that a group called "add-group" will collide with the static route and fail
   to load if linked directly from a URL.

Routing and the Viewer
----------------------

Part of the functionality of the :ref:`Viewer` is the ability to create dynamic
routes based on the visible item. For example, when you click on
``wheel`` in the Groups DetailViewer, the URL displayed in the browser bar
changes to ``myfreenas.local/accounts/groups/wheel`` and the item view for
``wheel`` displays.

The Viewer uses props of its own to render the correct item.

The Viewer requires an prop called ``viewData``, which in turn must contain a
an object called ``routing``. ``routing`` provides routing information
based on that in routes.js.

Our corresponding ``routing`` object in the Groups view will look like this:

.. code-block:: javascript

  routing = {
      "route"     : "groups-editor"
    , "param"     : "groupID"
    , "addentity" : "add-group"
  }

* ``route`` is the ``name`` property to which each item will linked.
* ``param`` is the name of the param that must be passed.
* ``addentity`` is the static route used for the special path
  pointing to the ``AddGroup`` component.

.. note:: There is far more to react-router than just the above. We strongly
   encourage all FreeNAS developers to become familiar with
   `react-router <https://github.com/rackt/react-router>`__ in depth.
