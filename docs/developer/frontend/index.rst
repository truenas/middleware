.. highlight:: javascript
   :linenothreshold: 5

FreeNAS 10 Frontend Development Guide
=====================================

.. toctree::
   :maxdepth: 1

   Glossary of Technologies <tech_glossary>
   Flux Architecture <flux>
   Webapp Architecture <webapp>
   Middleware Client <middleware>
   The Live Development Environment <develop>
   Widgets <widgets>
   The Viewer Component <viewer>
   Routing <routing>
   Adding a Viewer <adding_a_viewer>



Introduction
------------

This colleciton of documents (The Frontend Development Guide) describe
the fundamental architecture and underlying technologies employed by the
FreeNAS 10 GUI. It is not intended as a tutorial for git, JavaScript, or
any of the libraries or packages used by FreeNAS 10. Rather, it focuses
on the setup of a development environment, best practices, architecture,
separation of concerns, and functional summaries and glossaries of terms
which apply directly to the project.

Special attention is given to significant patterns and tools, such as
the :doc:`Flux Architecture <flux>` or :doc:`Middleware Client <middleware>`.
While these build on established libraries and patterns, it is often helpful to
understand the specific way in which they are applied to the FreeNAS 10 WebApp.
When possible, external documentation and articles are provided for
further reading.

Warning: Work in Progress!
~~~~~~~~~~~~~~~~~~~~~~~~~~

This guide is a work in progress, and as such, may contain incomplete
sections or factual inaccuracies. Please advise corey@ixsystems.com or
ben@ixsystems.com of any errors, confusing wording, etc. This guide aims to be a
clear and complete explanation of the new GUI, and all feedback is appreciated
along the way!

Changes From Previous Versions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

FreeNAS 10 is a clean-sheet re-write of the previous frontend, and
shares no code with the GUIs from versions 8 or 9. This version no
longer uses Python/Django toolkits to generate the display code; it’s
instead generated from JavaScript templates, using Facebook’s React.

This change affords the FreeNAS project much greater power and
flexibility in terms of its web interface, and removes the limitations
of a toolkit-based approach. It also enables an architectural shift to a
more modern web architecture, in which the web UI isn’t just a website
served by your FreeNAS instance, but a full-fledged web application,
capable of managing connections, internal state, relationships to other
FreeNAS devices, dropped connections, queued tasks, concurrent users,
and other improvements.

FreeNAS 10 Frontend Development
-------------------------------

:doc:`Glossary of Technologies <tech_glossary>`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Learn the name and function of packages and technologies used in the
FreeNAS 10 WebApp. This section includes author and license information,
and links to source code where available.

--------------

:doc:`Flux Architecture <flux>`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Data flow in the FreeNAS WebApp relies on the Flux architecture. This guide lays
out the entire data lifecycle from requests in the view to data being stored in
the app.

--------------

:doc:`Webapp Architecture <webapp>`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This section provides the layout of the FreeNAS WebApp and shows how the main
components are nested.

--------------

:doc:`Middleware Client <middleware>`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

All interaction between the FreeNAS WebApp and the middleware server goes
through the Middleware Client. This section documents all the WebApp-facing
functions of the Middleware Client. In the future, it will cover internal
functions as well.

--------------

:doc:`The Live Development Environment <develop>`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This guide explains how to setup and use the automated ``grunt`` tools
included with the FreeNAS 10 source code for live development and
automated webapp builds.

--------------

:doc:`Widgets <widgets>`
~~~~~~~~~~~~~~~~~~~~~~~~

This section covers how to implement a FreeNAS dashboard widget.

--------------

:doc:`The Viewer Component <viewer>`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The Viewer is the chief means of displaying data that comes in a list of items.
This section covers the props of the Viewer and each of its view modes.

--------------

:doc:`Routing <routing>`
~~~~~~~~~~~~~~~~~~~~~~~~

FreeNAS uses ``react-router`` for routing. This section covers FreeNAS' specific
use of react-router and common patterns.

--------------

:doc:`Adding a Viewer <adding_a_viewer>`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This section covers the whole process of adding a new viewer, following the Flux
lifecycle and making use of the information in the Viewer and Routing sections.