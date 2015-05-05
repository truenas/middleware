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
   First-Time Setup <setup>
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
the :doc:`Flux Architecture <flux>` or :doc:`Middleware Client <middleware>`. While these build on
established libraries and patterns, it is often helpful to understand
the specific way in which they are applied to the FreeNAS 10 WebApp.
When possible, external documentation and articles are provided for
further reading.

Warning: Work in Progress!
~~~~~~~~~~~~~~~~~~~~~~~~~~

This guide is a work in progress, and as such, may contain incomplete
sections or factual inaccuracies. Please advise corey@ixsystems.com of
any errors, confusing wording, etc. This guide aims to be a clear and
complete explanation of the new GUI, and all feedback is appreciated
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

:doc:`First-Time Setup <setup>`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Set up a development environment on your workstation. This guide
explains how to initialize the automated development environment, as
well as which tools and packages are required for your platform.

--------------

:doc:`The Live Development Environment <develop>`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This brief guide explains how to use the automated ``grunt`` tools
included with the FreeNAS 10 source code for live development and
automated webapp builds.

