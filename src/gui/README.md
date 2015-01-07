FreeNAS 10 Frontend Development Guide
=====================================

<img src="documentation/images/FreeNAS 10 Mockup.png" />

## Introduction
This colleciton of documents (The Frontend Development Guide) describe the fundamental architecture and underlying technologies employed by the FreeNAS 10 GUI. It is not intended as a tutorial for git, JavaScript, or any of the libraries or packages used by FreeNAS 10. Rather, it focuses on the setup of a development environment, best practices, architecture, separation of concerns, and functional summaries and glossaries of terms which apply directly to the project.

Special attention is given to significant patterns and tools, such as the [Flux Architecture](documentation/flux.md) or [Middleware Client](documentation/middleware.md). While these build on established libraries and patterns, it is often helpful to understand the specific way in which they are applied to the FreeNAS 10 WebApp. When possible, external documentation and articles are provided for further reading.

### Warning: Work in Progress!
This guide is a work in progress, and as such, may contain incomplete sections or factual inaccuracies. Please advise corey@ixsystems.com of any errors, confusing wording, etc. This guide aims to be a clear and complete explanation of the new GUI, and all feedback is appreciated along the way!

### Changes From Previous Versions
FreeNAS 10 is a clean-sheet re-write of the previous frontend, and shares no code with the GUIs from versions 8 or 9. This version no longer uses Python/Django toolkits to generate the display code; it's instead generated from JavaScript templates, using Facebook's [React](http://facebook.github.io/react).

This change affords the FreeNAS project much greater power and flexibility in terms of its web interface, and removes the limitations of a toolkit-based approach. It also enables an architectural shift to a more modern web architecture, in which the web UI isn't just a website served by your FreeNAS instance, but a full-fledged web application, capable of managing connections, internal state, relationships to other FreeNAS devices, dropped connections, queued tasks, concurrent users, and other improvements.


## FreeNAS 10 Frontend Development

#### [Glossary of Technologies](documentation/tech_glossary.md)
Learn the name and function of packages and technologies used in the FreeNAS 10 WebApp. This section includes author and license information, and links to source code where available.

---

#### [First-Time Setup](documentation/setup.md)
Set up a development environment on your workstation. This guide explains how to initialize the automated development environment, as well as which tools and packages are required for your platform.

---

#### [The Live Development Environment](documentation/develop.md)
This brief guide explains how to use the automated `grunt` tools included with the FreeNAS 10 source code for live development and automated webapp builds.

---

#### React Components (Coming soon)
For the time being, please refer to the official [React documentation](http://facebook.github.io/react/docs/getting-started.html).

---

#### [Flux Architecture](documentation/flux.md)
Explore the application architecture that the FreeNAS 10 WebApp uses to enforce a unidirectional data flow while maintaining consistent state throughout the entire system.

---

#### [Web Application Layers](documentation/webapp.md)
Explains the role and placement of controller-views and persistent navigation, as well as indicating where and how each area of the GUI sources its data.

---

#### [The Middleware Client](documentation/middleware.md)
An in-depth look at the functionality of the FreeNAS 10 Middleware Client, and a review of how it can be used in conjunction with the broader [Flux Architecture](documentation/flux.md).