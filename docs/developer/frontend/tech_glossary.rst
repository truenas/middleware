.. highlight:: javascript
   :linenothreshold: 5

Glossary of Technologies
========================

This guide aims to explain the name and function of technologies core to
the new webapp architecture in FreeNAS 10.

FAQs
----

Is Node.js a webserver?
~~~~~~~~~~~~~~~~~~~~~~~

No. Node.js is a serverside JavaScript environment. It contains all of
the component parts and APIs necessary to create a webserver, and many
good ones have been created on top of Node.js.

Where is jQuery?
~~~~~~~~~~~~~~~~

FreeNAS 10 does not use jQuery. jQuery was the savior of its time, but
performs four core functions which have been deprecated by the adoption
of newer technologies and the creation of purpose-built libraries.

1. DOM manipulation

    As all views in the FreeNAS 10 WebApp are React components,
    modifying React's in-browser representation of its virtual DOM can
    create an un-reconcilable state, and presents other unneccessary
    risks.

2. AJAX requests

    The FreeNAS 10 Middleware uses a persistent WebSocket connection to
    facilitate communication between client and server. For times when
    this isn't the right course of action, the syntax and adoption of
    `XMLHTTPRequest <https://developer.mozilla.org/en-US/docs/Web/API/XMLHttpRequest/Using_XMLHttpRequest>`__
    have stabilized enough that a dedicated library is unneccessary.

3. Animation

    See Velocity.js below.

4. Polyfills for old browsers

    As React.js features a `synthetic event
    system <http://facebook.github.io/react/docs/events.html>`__, many
    of the most commonly needed polyfills are no longer required. Since
    the target platforms for FreeNAS 10 must also support WebSockets,
    the number of browsers that support WebSockets and yet still have a
    need for polyfills for now-standard methods like ``map()`` is
    negligible, at best.

Glossary
--------

|Bootstrap|
~~~~~~~~~~~

Twitter Bootstrap
^^^^^^^^^^^^^^^^^

+---------------------------------------------------+---------------------------------------------------+----------------+---------------------------------------------------------------------+
| Homepage                                          | Source Code                                       | License Type   | Author                                                              |
+===================================================+===================================================+================+=====================================================================+
| `getbootstrap.com <http://getbootstrap.com/>`__   | `GitHub <https://github.com/twbs/bootstrap/>`__   | MIT            | [@mdo](https://github.com/mdo) and [@fat](https://github.com/fat)   |
+---------------------------------------------------+---------------------------------------------------+----------------+---------------------------------------------------------------------+

Twitter Bootstrap (TWBS) is one of the most popular and well-known HTML,
CSS, and JavaScript frameworks in use today. It has been widely adopted
in a variety of websites, from personal blogs to Fortune 500 companies.

The act of switching away from the toolkits used in previous versions of
FreeNAS has given the project more freedom, and more ways to accomplish
the same goals, but also introduced a lack of visible structure.
Primarily, the use of TWBS in FreeNAS 10 leverages a recognizable,
well-documented platform with a shallow learning curve, and promotes the
use of pre-existing patterns to design and organize content.

TWBS is used in FreeNAS 10 in a slightly unconventional way. Rather than
using the pre-packaged download, the LESS source files for TWBS are
compiled at build time, together with the FreeNAS 10 LESS files, to
create a single master stylesheet. The JavaScript components are not
included verbatim, but rather provided by `React
Bootstrap <http://react-bootstrap.github.io>`__, a companion library
that includes simple React reimplementations of the TWBS components.

--------------

|Bower|
~~~~~~~

Bower
^^^^^

+-----------------------------------+-----------------------------------------------+----------------+-----------------------------------------------------------------------------+
| Homepage                          | Source Code                                   | License Type   | Author                                                                      |
+===================================+===============================================+================+=============================================================================+
| `bower.io <http://bower.io/>`__   | `GitHub <https://github.com/bower/bower>`__   | MIT            | [@fat](https://github.com/fat) and [@maccman](https://github.com/maccman)   |
+-----------------------------------+-----------------------------------------------+----------------+-----------------------------------------------------------------------------+

Bower is a package management system for frontend libraries and plugins.
It focuses on compiled (and often minified) code which is ready to be
redistributed as-is. It functions as a counterpart to npm, and provides
packages like Twitter Bootstrap or Velocity.js.

--------------

|Browserify|
~~~~~~~~~~~~

+-----------------------------------------------+------------------------------------------------------------+----------------+--------------------------------------------+
| Homepage                                      | Source Code                                                | License Type   | Author                                     |
+===============================================+============================================================+================+============================================+
| `browserify.org <http://browserify.org/>`__   | `GitHub <https://github.com/substack/node-browserify>`__   | MIT            | [@substack](https://github.com/substack)   |
+-----------------------------------------------+------------------------------------------------------------+----------------+--------------------------------------------+

Browserify is a JavaScript bundler which concatenates and minifies a
webapp's many individual JavaScript module files into a single, indexed
bundle file. It uses a simple ``require()`` syntax (similar to the
native Node.js method) to "export" each module as an indexed object.
This has enormous benefits in a single-page webapp, as JavaScript
objects are singletons, and thus every view, module et al. will have
access to the same instance of each - conserving memory and simplifying
state reconciliation between React components.

.. code:: javascript

    var unique = require('uniq');

Browserify minimizes the number of requests that need to be made for
resources, ensures that the initial load will include all of the
application "run" code, and decouples source files' placement from their
final compiled "location".

--------------

|D3|
~~~~

Data Driven Documents
^^^^^^^^^^^^^^^^^^^^^

+-----------------------------------+-----------------------------------------------+-------------------------+--------------------------------------------+
| Homepage                          | Source Code                                   | License Type            | Author                                     |
+===================================+===============================================+=========================+============================================+
| `d3js.org <http://d3js.org/>`__   | `GitHub <https://github.com/mbostock/d3>`__   | Modified BSD 2-Clause   | [@mbostock](https://github.com/mbostock)   |
+-----------------------------------+-----------------------------------------------+-------------------------+--------------------------------------------+

D3.js is a JavaScript library for manipulating documents based on data.
It is capable of providing rich visualization in the form of charts,
graphs, maps, and more. In particular, it's used for FreeNAS 10's system
overview, providing realtime graphs of CPU, network, disk, etc.

--------------

|Grunt|
~~~~~~~

+-----------------------------------------+-------------------------------------------------------+----------------+------------------------------------------------------------+
| Homepage                                | Source Code                                           | License Type   | Author                                                     |
+=========================================+=======================================================+================+============================================================+
| `gruntjs.com <http://gruntjs.com/>`__   | `Project on GitHub <https://github.com/gruntjs/>`__   | MIT            | `Grunt Dev Team <http://gruntjs.com/development-team>`__   |
+-----------------------------------------+-------------------------------------------------------+----------------+------------------------------------------------------------+

Grunt is a JavaScript task runner, which allows developers to specify
tasks and build pipelines. It can be used to automatically compile code,
restart webservers, parallelize tasks, and can be extended to almost any
functionality. Grunt runs the tasks that compile LESS to CSS, uglify and
unit test JavaScript, create Browserify bundles, and more.

FreeNAS 10 uses Grunt most visibily in the live development environment,
where a series of concurrent file watchers are run, set up to trigger
everything from CSS rebuilds to restarting the FreeNAS development
target over ``ssh``.

--------------

|LESS|
~~~~~~

+-----------------------------------------+------------------------------------------------+----------------+----------------------------------------------+
| Homepage                                | Source Code                                    | License Type   | Author                                       |
+=========================================+================================================+================+==============================================+
| `lesscss.org <http://lesscss.org/>`__   | `GitHub <https://github.com/less/less.js>`__   | Apache         | [@cloudhead](https://github.com/cloudhead)   |
+-----------------------------------------+------------------------------------------------+----------------+----------------------------------------------+

LESS is a CSS-like language which compiles to CSS. It features
variables, mixins, and heirarchical class declarations which make
development simpler. LESS can also be split into several different
files, keeping projects neater and better organized.

LESS is used in FreeNAS 10 primarily for its utility, and because
Twitter Bootstrap is based on LESS. Compiling from LESS creates a
single, unified file with less overwrites or complicated rules. The
mixin architecture allows for powerful and dynamic expressions, as well
as a simpler development process.

--------------

|Node|
~~~~~~

+---------------------------------------+-----------------------------------------------+----------------+----------------------------------------+
| Homepage                              | Source Code                                   | License Type   | Author                                 |
+=======================================+===============================================+================+========================================+
| `nodejs.org <http://nodejs.org/>`__   | `GitHub <https://github.com/joyent/node>`__   | MIT            | [@joyent](https://github.com/joyent)   |
+---------------------------------------+-----------------------------------------------+----------------+----------------------------------------+

*Node.js is not a webserver.*

Node.js is a serverside JavaScript environment based on Chromium's V8
engine. It is used to build web applications, run webservers, operate
task runners like Grunt, cross-compile code, and more.

Running a Node.js process on FreeNAS allows for things like serverside
rendering of JavaScript templates, prefetched state, and shared
callbacks between client and server.

--------------

|NPM|
~~~~~

+-----------------------------------------+-------------------------------------------+------------------------+-------------+
| Homepage                                | Source Code                               | License Type           | Author      |
+=========================================+===========================================+========================+=============+
| `npmjs.org <https://www.npmjs.org>`__   | `GitHub <https://github.com/npm/npm>`__   | Artistic License 2.0   | npm, Inc.   |
+-----------------------------------------+-------------------------------------------+------------------------+-------------+

npm is the package manager used by Node. It manages the libraries,
dependencies, Grunt plugins, and other development tools used in the
creation of a Node webapp. npm is primarily used for libraries and
modules which will be ``require()``'d inside of the application code,
such as React.

--------------

|React|
~~~~~~~

+--------------------------------------------------------------------+--------------------------------------------------+----------------+--------------------------------------+
| Homepage                                                           | Source Code                                      | License Type   | Author                               |
+====================================================================+==================================================+================+======================================+
| `facebook.github.io/react/ <http://facebook.github.io/react/>`__   | `GitHub <https://github.com/facebook/react>`__   | Apache 2.0     | Facebook & Instagram collaboration   |
+--------------------------------------------------------------------+--------------------------------------------------+----------------+--------------------------------------+

React is a JavaScript library for creating user interfaces. It is unlike
MVC frameworks like Ember, Backbone, or Angular. React aims only to
provide self-updating, dynamic views. React uses a virtual DOM and
hashes changes to the in-browser DOM, so its event-system, templates,
and supported features are properly represented across all browsers,
regardless of age.

React is rendered serverside in FreeNAS 10, so that the initial payload
sent to the user contains the HTML output of the React template, the
virtual DOM is preloaded, and the component's state is already
initialized.

Because React focuses on creating "components" instead of "pages", it
also works well with Browserify's ``require('foo')`` syntax to keep
files short, legible, and well organized. Components ``require()`` each
other, creating a visible nested heirarchy.

Developers who are familiar with writing static HTML pages should be
quickly familiar with React's pseudo-HTML syntax, which provides both a
gentle learning curve and valid semantic abstractions for the JavaScript
it represents.

--------------

|Velocity|
~~~~~~~~~~

+----------------------------------------------------------------------------+----------------------------------------------------------+----------------+------------------------------------------------------+
| Homepage                                                                   | Source Code                                              | License Type   | Author                                               |
+============================================================================+==========================================================+================+======================================================+
| `julian.com/research/velocity/ <http://julian.com/research/velocity/>`__   | `GitHub <https://github.com/julianshapiro/velocity>`__   | MIT            | [@julianshapiro](https://github.com/julianshapiro)   |
+----------------------------------------------------------------------------+----------------------------------------------------------+----------------+------------------------------------------------------+

Velocity is a ground-up reimplementation of jQuery's ``$.animate()``
function. It's lightweight, and more performant in all cases. It also
allows FreeNAS 10 to be completely free of jQuery, saving page weight
and complexity.

.. |Bootstrap| image:: images/glossary/Bootstrap.png
.. |Bower| image:: images/glossary/Bower.png
.. |Browserify| image:: images/glossary/Browserify.png
.. |D3| image:: images/glossary/D3.png
.. |Grunt| image:: images/glossary/Grunt.png
.. |LESS| image:: images/glossary/LESS.png
.. |Node| image:: images/glossary/Node.png
.. |NPM| image:: images/glossary/NPM.png
.. |React| image:: images/glossary/React.png
.. |Velocity| image:: images/glossary/Velocity.png
