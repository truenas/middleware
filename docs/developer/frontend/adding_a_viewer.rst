.. highlight:: javascript
   :linenothreshold: 5

Adding a New Viewer
===================

This guide explains the process of creating a new view in the FreeNAS 10 GUI.
A view is used to display data and will usually provide means to search through
a list of items and edit each one. Examples of views are [FreeNAS URL]/Accounts/Users
and [FreeNAS URL]/Services. This guide will use the implmentation of the Groups
view as an example to show the entire implmentation process from beginning to end.

What is the Viewer?
-------------------

In simplest terms, the Viewer is a multipurpose React Component
(controller-view) which displays arbitrary data returned by the FreeNAS
10 Middleware Server. It has several different sub-views, which each
sort the data in a different way.

The parent controller-view is responsible for maintaining state,
indicating subscription changes to the Middleware Client, and handling
the propagation of data to its children.

Flux
----

This guide will rely heavily on :ref:`Flux`. It's worth having that full
guide open alongside this one. This diagram, in particular, is going to
dictate the steps we work through as we create the new Viewer instance.

.. figure:: images/architecture/flux/freenas_flux.png
   :alt: A high level data flow diagram for FreeNAS 10's UI

   A high level data flow diagram for FreeNAS 10's UI
A New Viewer
------------

A completely blank, basic view might look something like the example below.
This is currently doing nothing but displaying an ``<h2>`` tag within ``<main>``
- which is the expected "base" tag in any Primary View.

.. code-block:: javascript

  // Groups
  // ======
  // Viewer for FreeNAS groups.

  "use strict";


  var React = require("react");

  var Groups = React.createClass({
    render: function() {
      return (
        <main>
          <h2>Groups View</h2>
        </main>
      );
    }
  });

  module.exports = Groups;

Fleshing out a View
-------------------

Now we'll add some of the boilerplate that each Viewer instance
requires.

Require the Modules
~~~~~~~~~~~~~~~~~~~

The first step is to require everything we're about to need for this
controller-view. The Viewer component itself is required, and eventual
references will be made to the item view template, the Middleware
Utility Class, and the Flux Store which will have the data we want.

.. code-block:: javascript

  var React = require("react");

  var Viewer = require("../components/Viewer");

  // var GroupItem =

  // var GroupsMiddleware =
  // var GroupsStore      =

Include Format Data
~~~~~~~~~~~~~~~~~~~

*WARNING:* This is subject to change.

Currently, each Viewer instance relies on a JSON file with some display
information. Really, this could be provided any other way. In the
future, it might be provided by the Middleware Server as companion
metadata to new types of data provided on the same channel.

What it does is take the response returned by the Middleware Server and
tell the Viewer how to regard different types of data. The Viewer
expects to know a few things, like what the "primary" and "secondary"
keys are (these are used in certain display modes, and also for
searching).

In the future, searching will probably be based on a combination of
preselected keys.

The current functional information contained by the display JSON file is
something like this:

.. code:: javascript


        [{
            "primaryKey"   : "username"   // Displays prominently, is searchable
          , "secondaryKey" : "full_name"  // Also searchable, displays as companion text
          , "selectionKey" : "username"   // Used in URLs and other selections
          , "imageKey"     : "user_icon"  // (Optional) A base64 encoded string to use as the image
          , "uniqueKey"    : "id"         // (Optional) A reliably unique key
          , "dataKeys": [
              {
                  "key"         : "builtin"       // One of the keys in a returned object
                , "name"        : "Built-in User" // Human readable name for key
                , "type"        : "boolean"       // (Optional) Used for type checking
                , "defaultCol"  : true            // Should be used as a column in TableViewer by default
              }

              // ...

            ]
        }]

So then, when looking at the Middleware Server response for
``service.query``, we can see this:

.. code:: javascript


        [
          {
              "state": "stopped",
              "name": "ftp"
          },
          {
              "state": "running",
              "pid": 629,
              "name": "devd"
          },
          {
              "state": "stopped",
              "name": "snmp"
          },
          {
              "state": "running",
              "pid": 939,
              "name": "nginx"
          },
          {
              "state": "running",
              "pid": 715,
              "name": "syslog"
          },
          {
              "state": "running",
              "pid": 1032,
              "name": "sshd"
          },
          {
              "state": "unknown",
              "name": "nfs"
          }
        ]

Based on that, we can see that we have three keys: ``state``, ``pid``,
and ``name``. ``pid`` is clearly only provided if the state is "running"
- something we'll want to take into account later on.

Therefore, ``services-display.json`` might look like:

.. code:: javascript


        [{
            "primaryKey"   : "name"
          , "secondaryKey" : "state"
          , "selectionKey" : "name"
          , "dataKeys": [
              {
                  "key"         : "name"
                , "name"        : "Service"
                , "type"        : "string"
                , "defaultCol"  : true
              }
            , {
                  "key"         : "state"
                , "name"        : "Status"
                , "type"        : "string"
                , "defaultCol"  : true
              }
            , {
                  "key"         : "pid"
                , "name"        : "PID"
                , "type"        : "number"
                , "defaultCol"  : true
              }
          ]
    }]

It's then required, like everything else:

.. code:: javascript


        var formatData = require("../../data/middleware-keys/services-display.json")[0];

    *To make this follow the workflow little bit better I will prefer if
    the data displaying part was following the previous paragraphs.
    Dynamic Routing and Filteres/Groups are important, but maybe too
    distracting in this moment. First I want to see the data somehow and
    afterwards worry abour routing and organizing them.* ## Dynamic
    Routing Because the FreeNAS 10 GUI uses client-side routing, the
    page is never refreshed or changed during a session. One of the
    interesting effects of this is the ability to use client-side
    routing - meaning that as the visible React components are changed
    or selected, the route in the browser bar changes to reflect that.

Part of the functionality of the viewer is the ability to create dynamic
routes based on the visible item. For example, when you click on
``root`` in the Users DetailViewer, the URL displayed in the browser bar
changes to ``myfreenas.local/accounts/users/root``.

This is not automatic, however, and some setup is required to make it
work.

The Viewer requires an object called ``itemData`` which provides routing
information, based on predefined routes in ``routes.js``.

For instance, if we set up ``routes.js`` such that

.. code:: javascript


        <Route name="services" handler={ Services }>
          <Route name    = "services-editor"
                 path    = "/services/:serviceID"
                 handler = { Editor }
        </Route>

our cooresponding ``itemData`` object in the Services view will look
something like this:

.. code:: javascript


        var itemData = {
            "route" : "services-editor"
          , "param" : "serviceID"
        };

"Route" is the "name" property given to the ``<Route>`` in
``routes.js``. "Param" is the variable part of the path.

Filters and Groups
------------------

Viewers understand the concept of filters and groups, which allow raw
Middleware responses to be sorted into different categories, or hidden
from the default View (this functionality may be removed soon).

Filters control whether content is displayed. They're applied first.

Groups sort content into defined categories, as well as a "remaining"
section.

Both of these rely on the ``filterCriteria`` object.

The order of criteria in either array is the same order in which they'll
render in the Viewer.

Putting it all together, we're able to create our ``displaySettings``
object. This is similar to the display JSON file, and is subject to the
same potential future rewrite.

.. code:: javascript


        var displaySettings = {
            filterCriteria: {
                stopped: {
                    name     : "stopped processes"
                  , testProp : { "state": "stopped" }
                }
            }
          , remainingName  : "other services"
          , ungroupedName  : "all services"
          , allowedFilters : [ ]
          , defaultFilters : [ ]
          , allowedGroups  : [ "running", stopped" ]
          , defaultGroups  : [ "running", stopped" ]
        };

What the above tells us is that we're going to sort processes by their
running state, and then anything that doesn't fit into either of those
will be in "remaining".

We aren't filtering anything by default, and we aren't even allowing
filters. If there were a category of services that was being returned,
and was somehow irrelevant to the user, we could add it to
``defaultFilters`` to hide it when the Viewer is initialized.

The "name" property here is a little different, and that's because it's
expected to be part of a sentence, or a menu entry, or a heading in the
DetailViewer or IconViewer.

Viewer Lifecycle
----------------

Each Viewer instance leverages the React lifecycle pretty heavily to get
set up the right way.

Here's what we're going to need in addition to ``render``:

.. code:: javascript


          getInitialState: function() {
            // ...
          }

        , componentDidMount: function() {
            // ...
          }

        , componentWillUnmount: function() {
            // ...
          }

In ``getInitialState``, what we'd really like to do is get the Services
data out of our Flux store and use them to initialize state. Only one
problem: we don't have a Flux store yet!

Instead of trying to solve that problem right away (and to keep things
simple), we're going to walk through the diagram in order. >\ *I like
this part. It is comforting for the reader. You have a plan. :-)*

.. figure:: images/architecture/flux/freenas_flux.png
   :alt: A high level data flow diagram for FreeNAS 10's UI

   A high level data flow diagram for FreeNAS 10's UI
Based on that, the next thing we need is a Middleware Utility Class.

Middleware Utility Class
------------------------

In this class, we just need a single public method connected to the
Middleware Client with a callback to the ServicesActionCreators (which
also don't exist yet).

Looking at the middleware debugger, we can see that the right call is
``service.query``. Later, we can expect this to be pluralized to match
everything else. >\ *Maybe add more about activating the debug mode?*

Our Middleware Utility Class looks something like this:

.. code:: javascript


        // Services Middleware
        // ===================

        "use strict";

        var MiddlewareClient = require("../middleware/MiddlewareClient");

        var ServicesActionCreators = require("../actions/ServicesActionCreators");

        module.exports = {

          requestServicesList: function() {
              MiddlewareClient.request( "service.query", [], function ( rawServicesList ) {
                ServicesActionCreators.receiveServicesList( rawServicesList );
              });
          }

        };

ActionCreators
--------------

After that call returns from the Middleware, we need to handle the raw
data. We assumed a function called ``receiveServicesList`` in our MUC's
``requestServicesList`` function, so that's what we need to create now.

All it has to do here is tag the payload with a sensible action type,
and provide the returned raw data as another parameter. These will be
caught by the Flux store we're about to create (and ignored by all the
other Flux stores).

This ActionCreator will then call the dispatcher and broadcast this
payload to all registered Flux stores.

.. code:: javascript


        // Services Action Creators
        // ==================================

        "use strict";

        var FreeNASDispatcher = require("../dispatcher/FreeNASDispatcher");
        var FreeNASConstants  = require("../constants/FreeNASConstants");

        var ActionTypes = FreeNASConstants.ActionTypes;

        module.exports = {

            receieveServicesList: function( rawServices ) {
              FreeNASDispatcher.handleMiddlewareAction({
                  type        : ActionTypes.RECEIVE_RAW_SERVICES
                , rawServices : rawServices
              });
            }

        };

FreeNASConstants
----------------

We'll need to jump into ``FreeNASConstants.js`` to add a key-value pair
for ``RECEIVE_RAW_SERVICES``. Don't forget to do this.

Flux Store
----------

The Flux stores unfortunately have a lot of boilerplate. I'm working on
reducing this - likely will have them all inherit from more things in
the future.

.. code:: javascript


        // Services Flux Store
        // ----------------

        "use strict";

It uses Lodash, mostly for its ``_.assign()`` function.

.. code:: javascript


        var _            = require("lodash");

One of the most important functions that a Flux store performs is that
it also behaves as an EventEmitter.

.. code:: javascript


        var EventEmitter = require("events").EventEmitter;

It requires the Dispatcher and the Constants (for the ActionTypes).

.. code:: javascript


        var FreeNASDispatcher = require("../dispatcher/FreeNASDispatcher");
        var FreeNASConstants  = require("../constants/FreeNASConstants");

        var ActionTypes  = FreeNASConstants.ActionTypes;

We need to define a change event, just so that all the EventEmitter
stuff can all use the same one.

.. code:: javascript


        var CHANGE_EVENT = "change";

And finally, we'll define ``_services``, which is the actual beating
heart of the Flux Store. This variable is what will ACTUALLY be modified
and updated when the Middleware sends new data. It's just a normal
JavaScript object with no hidden attributes or special sauce.

.. code:: javascript


        var _services = [];

Now, we create the object for ``ServicesStore`` and assign the
EventEmitter prototype to it (this gives it all the EventEmitter
methods).

We'll also need three of our own methods - a way to emit a change (used
internally), a way for a React component to "listen" to the store and
know when it updates, and a way for it to stop doing that.

On top of those, we need what we came here for - a way to get an
up-to-date list of the services, right out of the ``_services`` array.

.. code:: javascript


        var ServicesStore = _.assign( {}, EventEmitter.prototype, {

            emitChange: function() {
              this.emit( CHANGE_EVENT );
            }

          , addChangeListener: function( callback ) {
              this.on( CHANGE_EVENT, callback );
            }

          , removeChangeListener: function( callback ) {
              this.removeListener( CHANGE_EVENT, callback );
            }

          , getAllServices: function() {
              return _services;
            }

        });

Now we just need to register ``ServicesStore`` with the
``FreeNASDispatcher``, and add a switch-case to look for the ActionType
we defined in our ServicesActionCreator.

.. code:: javascript


        ServicesStore.dispatchToken = FreeNASDispatcher.register( function( payload ) {
          var action = payload.action;

          switch( action.type ) {

            case ActionTypes.RECEIVE_RAW_SERVICES:
              _services = action.rawServices;
              ServicesStore.emitChange();
              break;

            default:
              // No action
          }
        });

Oh, and don't forget your ``module.exports``.

.. code:: javascript


        module.exports = ServicesStore;

    *It is a good reminder, but don't you unnecessarily break up the
    code?*

Back to the Lifecycle
---------------------

Finally, we have some stuff to plumb into the React Lifecycle.

Let's go back up and continue to fill in our list of requires. We should
now only be missing the Item template.

.. code:: javascript


        var ServicesMiddleware = require("../middleware/ServicesMiddleware");
        var ServicesStore      = require("../stores/ServicesStore");

First, let's make a private method that we can use to quickly get the
list of services out of the store, whenever we need to (we'll know we
need to because the listener will call this later).

In this case, it's pretty simple, but if we needed to ``concat()`` data
from another store, or some hard-coded values, or do some other data
merging, this would be a very convenient place.

.. code:: javascript


        function getServicesFromStore() {
          return {
            usersList: ServicesStore.getAllServices()
          };
        }

Now we can fill in the lifecycle methods.

.. code:: javascript


          getInitialState: function() {
            return getServicesFromStore();
          }

        , componentDidMount: function() {
            ServicesMiddleware.requestUsersList();

            ServicesStore.addChangeListener( this.handleServicesChange );
          }

        , componentWillUnmount: function() {
            ServicesStore.removeChangeListener( this.handleServicesChange );
          }

As you can probably tell, this initializes state with our utility
function, which is important every time but the very first - since
Stores are singletons and they're totally separate from the
views/components, anything we've previously put in the store, either
from another view, or from opening this view previously will still be in
there, giving us a faster initialization without a flash of unstyled
content (nice!). >\ *This is not important, but I was once told that
phrases like "As you can probably tell" sounds condescending to the
readers.*

When the component mounts, it subscribes to the Services store, and when
it unmounts, it unsubscribes.

The only difference is that ``componentDidMount`` also calls our
original ``requestServicesList`` function, asking the Middleware for an
initial payload.

(This is also where subscriptions will be handled, but they're not
implemented yet.)

You may also notice that I made reference to another method that doesn't
exist yet - ``handleServicesChange``. This is a convenient method we'll
create just so that we have a single function for updating our
controller-view's state. For now, it's basically the same thing we did
in ``getInitialState``.

.. code:: javascript


        , handleServicesChange: function() {
            this.setState( getServicesFromStore() );
          }

The Actual Viewer Component
---------------------------

Now that we've gone and done all that, we can finally implement the
actual ``<Viewer>`` in ``render``. All the setup we've done is finally
going to pay off, as we plug everything into the Viewer component.

As before, we're still missing the ItemView, which the Viewer will need.

.. code:: javascript


        , render: function() {
            return (
              <main>
                <h2>Services</h2>
                <Viewer header      = { "Services" }
                        inputData   = { this.state.servicesList }
                        displayData = { displaySettings }
                        formatData  = { formatData }
                        itemData    = { itemData }
                        Editor      = { this.props.activeRouteHandler }>
                </Viewer>
              </main>
            );
          }

A Note on Debugging
-------------------

Now that we're ready to actually check our work, it can be helpful to
change this value in ``MiddlewareClient.js``:

.. code:: javascript


          // Change DEBUG to `true` to activate verbose console messages
          var DEBUG = true;

This will cause the JavaScript console to contain very detailed messages
about exactly what the Middleware Client is doing, what responses are
being seen, and how they're being treated.

Disallowing Viewer Modes
------------------------

Creating an Item Template
-------------------------

    *Can you maybe add the names of used files/functions to the diagram?
    It will visually demonstrate, where in this tutorial we are relative
    to the more abstract diagram.*
