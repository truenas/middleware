freenas-gui
===========

The official repository for the web GUI used in FreeNAS 10+

<img src="documentation/images/FreeNAS 10 Mockup.png" />

## FreeNAS 10 GUI tools - High Level Overview
FreeNAS 10 dispenses with the django-based UI used in 8.x and 9.x and replaces it with an entire new GUI based on node.js. One of the benefits of this is that changes to the UI can be made, tested, and disposed of quickly, instead of waiting for a compilation cycle to make sure everything worked out correctly. This is the tool that makes that work.

### Guides for Getting Started
These are not tutorials on node.js, npm, grunt, git, or any of the other tools used along the way. These are just guides to get you started developing the new FreeNAS GUI.

1. [Set up your Development Environment](documentation/setup.md)
2. [Developing for FreeNAS 10](documentation/develop.md)
